import os
import subprocess
import pickle  # 用于序列化 declaration map
from typing import Dict, List
import asyncio
import aiofiles
import aiofiles.os
from datetime import datetime

from copx.symbal_extractor.symbol_extractor import extract_symbols_from_file
from copx.utils import iter_project_files

#####################
# 1. Git管理模块
#####################


async def _run_subprocess(
    cmd_parts: List[str], cwd: str, env: Dict = None, check: bool = True
):
    process = await asyncio.create_subprocess_exec(
        *cmd_parts,
        cwd=cwd,
        env=env or os.environ.copy(),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    if check and process.returncode != 0:
        raise subprocess.CalledProcessError(
            process.returncode, cmd_parts, output=stdout, stderr=stderr
        )
    return (
        stdout.decode().strip() if stdout else "",
        stderr.decode().strip() if stderr else "",
    )


async def setup_repo_identity(
    git_dir, name="CodeQA_Tool", email="noreply@codeqa.local"
):
    env = os.environ.copy()
    await _run_subprocess(["git", "config", "user.name", name], cwd=git_dir, env=env)
    await _run_subprocess(["git", "config", "user.email", email], cwd=git_dir, env=env)


class ProjectGitManager:
    def __init__(self, project_path: str, git_root: str):
        self.project_path = os.path.abspath(project_path)
        self.git_path = os.path.join(os.path.abspath(git_root), self._project_id())
        self.git_dir = os.path.join(self.git_path, ".git")

    async def initialize_if_needed(self):
        if not await asyncio.to_thread(os.path.exists, self.git_path):
            await asyncio.to_thread(os.makedirs, self.git_path, exist_ok=True)

    def _project_id(self):
        return os.path.basename(self.project_path).replace(" ", "_")

    async def ensure_git_repo(self):
        """初始化 git 仓库（若未存在）"""
        await self.initialize_if_needed()  # Ensure base path exists
        if not await aiofiles.os.path.exists(self.git_dir):
            await _run_subprocess(["git", "init"], cwd=self.git_path)
            await setup_repo_identity(self.git_dir)
            async with aiofiles.open(
                os.path.join(self.git_path, ".gitignore"), "w"
            ) as f:
                await f.write(".gitignore\n")

    def git_env(self):
        return {
            "GIT_DIR": self.git_dir,
            "GIT_WORK_TREE": self.project_path,
            "PATH": os.environ["PATH"],
        }

    async def snapshot(self):
        """将 project 当前文件快照提交到 hidden git repo"""
        env = self.git_env()
        await _run_subprocess(["git", "add", "."], cwd=self.project_path, env=env)
        await _run_subprocess(
            [
                "git",
                "commit",
                "-m",
                f"Snapshot at {datetime.now().isoformat()}",
                "--allow-empty",
            ],
            cwd=self.project_path,
            env=env,
        )

    async def get_changed_files(self) -> List[str]:
        """返回两次提交间所有有变动的文件路径（相对 project 根路径）"""
        env = self.git_env()
        commit_count_str, _ = await _run_subprocess(
            ["git", "rev-list", "--count", "HEAD"],
            cwd=self.project_path,
            env=env,
        )
        commit_count = int(commit_count_str) if commit_count_str else 0

        if commit_count < 2:
            # 首次快照/首次运行时，全量处理
            # Assuming iter_project_files is synchronous and might do I/O
            # We run it in a thread to avoid blocking the event loop.
            def _sync_iter_project_files():
                all_files = []
                for root, _, files in iter_project_files(self.project_path):
                    for f_name in files:
                        if not root.startswith(self.git_path):
                            all_files.append(
                                os.path.relpath(
                                    os.path.join(root, f_name), self.project_path
                                )
                            )
                return all_files

            return await asyncio.to_thread(_sync_iter_project_files)

        result_stdout, _ = await _run_subprocess(
            ["git", "diff", "--name-only", "HEAD~1", "HEAD"],
            cwd=self.project_path,
            env=env,
        )
        changed_files = []
        for line in result_stdout.splitlines():
            stripped_line = line.strip()
            if stripped_line and await aiofiles.os.path.isfile(
                os.path.join(self.project_path, stripped_line)
            ):
                changed_files.append(stripped_line)
        return changed_files

    async def get_head_commit(self):
        env = self.git_env()
        stdout, _ = await _run_subprocess(
            ["git", "rev-parse", "HEAD"], cwd=self.project_path, env=env
        )
        return stdout

    async def get_commits_between(self, old_commit, new_commit):
        env = self.git_env()
        stdout, _ = await _run_subprocess(
            ["git", "rev-list", "--reverse", f"{old_commit}..{new_commit}"],
            cwd=self.project_path,
            env=env,
        )
        return stdout.splitlines()

    async def get_changed_files_between_commits(self, c1, c2):
        env = self.git_env()
        stdout, _ = await _run_subprocess(
            ["git", "diff", "--name-only", f"{c1}", f"{c2}"],
            cwd=self.project_path,
            env=env,
        )
        return [l.strip() for l in stdout.splitlines() if l.strip()]

    async def has_head_commit(self):
        env = self.git_env()
        try:
            out_str, _ = await _run_subprocess(
                ["git", "rev-list", "--count", "HEAD"],
                cwd=self.project_path,
                env=env,
            )
            return int(out_str) > 0 if out_str else False
        except (
            subprocess.CalledProcessError
        ):  # If HEAD doesn't exist, rev-list might error
            return False
        except Exception:
            return False


##########################
# 2. Declaration Map管理模块
##########################


class DeclarationMapManager:
    def __init__(self, project_path: str, hidden_git_root_path: str):
        self.project_path = project_path
        self.decl_map_file = os.path.join(
            hidden_git_root_path,
            os.path.basename(self.project_path).replace(" ", "_"),
            ".my_tool_decl_map.pkl",
        )
        self.commit_id = None
        self.declaration_map = {}

    async def load_decl_map(self):
        tmp_file = self.decl_map_file + ".tmp"
        if await aiofiles.os.path.exists(tmp_file):
            await aiofiles.os.replace(tmp_file, self.decl_map_file)
        if await aiofiles.os.path.exists(self.decl_map_file):
            try:
                async with aiofiles.open(self.decl_map_file, "rb") as f:
                    content = await f.read()
                    data = await asyncio.to_thread(pickle.loads, content)
                    self.declaration_map, self.commit_id = data
                    return
            except Exception as e:
                print(f"Error loading declaration map {self.decl_map_file}: {e}")
        self.declaration_map, self.commit_id = {}, None

    async def save_decl_map(self, commit_id: str):
        tmp_file = self.decl_map_file + ".tmp"
        try:
            data_to_pickle = (self.declaration_map, commit_id)
            pickled_data = await asyncio.to_thread(pickle.dumps, data_to_pickle)
            async with aiofiles.open(tmp_file, "wb") as f:
                await f.write(pickled_data)
                await f.flush()
            await aiofiles.os.replace(tmp_file, self.decl_map_file)
        except Exception as e:
            print(f"Error saving declaration map to {self.decl_map_file}: {e}")

    def remove_file_declarations(self, file_path: str):
        if file_path in self.declaration_map:
            del self.declaration_map[file_path]

    def update_file_declarations(self, file_path: str, symbols: List[dict]):
        print(f"save {file_path} for {symbols}")
        self.declaration_map[file_path] = symbols

    def get_all_declarations(self) -> List[dict]:
        all_syms = []
        for file_path, symbols in self.declaration_map.items():
            for s in symbols:
                s_copy = dict(s)
                s_copy["file"] = file_path
                all_syms.append(s_copy)
        return all_syms


####################
# 3. 主协调函数
####################


async def update_project_declaration_map(project_path, hidden_git_root_path):
    pgm = ProjectGitManager(project_path, hidden_git_root_path)
    await pgm.ensure_git_repo()
    dmm = DeclarationMapManager(project_path, hidden_git_root_path)
    await dmm.load_decl_map()  # Load existing map and commit_id

    if not await pgm.has_head_commit():
        # 首次运行：全量检查所有源码文件
        def _sync_iter_project_files_for_initial_scan():
            file_list_sync = []
            for root, _, files in iter_project_files(project_path):
                for f_name in files:
                    if (
                        not root.startswith(
                            os.path.join(project_path, ".my_tool_cache")
                        )
                        and not root.startswith(os.path.join(project_path, ".git"))
                        and not root.startswith(pgm.git_path)
                    ):  # Also exclude our hidden git repo
                        file_list_sync.append(
                            os.path.relpath(os.path.join(root, f_name), project_path)
                        )
            return file_list_sync

        file_list = await asyncio.to_thread(_sync_iter_project_files_for_initial_scan)

        tasks = []
        for file_rel_path in file_list:
            abs_file = os.path.join(project_path, file_rel_path)

            # Create a task for each file processing
            async def process_file(file_rel_path_inner, abs_file_inner):
                try:
                    symbols = await extract_symbols_from_file(abs_file_inner)
                    if symbols is not None and len(symbols) > 0:
                        return file_rel_path_inner, symbols
                except Exception as e_file:
                    print(f"分析{file_rel_path_inner}失败: {e_file}")
                return file_rel_path_inner, None

            tasks.append(process_file(file_rel_path, abs_file))

        results = await asyncio.gather(*tasks)
        for file_rel_path_res, symbols_res in results:
            if symbols_res:
                dmm.update_file_declarations(file_rel_path_res, symbols_res)

        await pgm.snapshot()
        head_id = await pgm.get_head_commit()
        await dmm.save_decl_map(head_id)
        return dmm.declaration_map, file_list

    current_head = await pgm.get_head_commit()
    last_map_commit = dmm.commit_id

    changed_files_overall = []

    if last_map_commit and last_map_commit != current_head:
        commits_to_replay = await pgm.get_commits_between(last_map_commit, current_head)
        files_changed_in_catchup = set()
        for commit in commits_to_replay:
            prev = f"{commit}~1"
            # Check if prev commit exists, otherwise diff from root tree of commit
            try:
                await pgm.get_head_commit()  # A way to check if repo is not empty
                # A more robust check would be to see if 'prev' is a valid ref
            except subprocess.CalledProcessError:
                # Handle case where prev might not exist (e.g. first commit in replay range)
                # This part might need more robust git logic for edge cases
                pass  # For now, assume prev exists or diff handles it

            files_this_commit = await pgm.get_changed_files_between_commits(
                prev, commit
            )
            for f in files_this_commit:
                files_changed_in_catchup.add(f)

        tasks_catchup = []
        for file_rel_path in files_changed_in_catchup:
            abs_file = os.path.join(project_path, file_rel_path)
            dmm.remove_file_declarations(file_rel_path)  # Remove old first

            async def process_file_catchup(file_rel_path_inner, abs_file_inner):
                if await aiofiles.os.path.exists(abs_file_inner):
                    try:
                        symbols = await extract_symbols_from_file(abs_file_inner)
                        if symbols is not None and len(symbols) > 0:
                            return file_rel_path_inner, symbols
                    except Exception as e_file:
                        print(f"补分析{file_rel_path_inner}时失败: {e_file}")
                return file_rel_path_inner, None

            tasks_catchup.append(process_file_catchup(file_rel_path, abs_file))

        results_catchup = await asyncio.gather(*tasks_catchup)
        for file_rel_path_res, symbols_res in results_catchup:
            if symbols_res:
                dmm.update_file_declarations(file_rel_path_res, symbols_res)

        await dmm.save_decl_map(current_head)
        changed_files_overall.extend(
            list(files_changed_in_catchup)
        )  # Report these as changed
        # After catch-up, the map is aligned with current_head. No further snapshot diff needed for this run.
        return dmm.declaration_map, changed_files_overall

    # Normal snapshot and diff if no catch-up was performed or if catch-up didn't align to current_head (should not happen with current logic)
    await pgm.snapshot()
    new_head = await pgm.get_head_commit()

    # If last_map_commit is None (e.g. map existed but commit_id was None), diff against parent of new_head
    # If last_map_commit is same as new_head (no changes since last run), diff might be empty.
    # If repo was empty before snapshot, new_head~1 might not exist. Git diff handles this by diffing against empty tree.
    diff_base = (
        last_map_commit
        if last_map_commit and last_map_commit != new_head
        else f"{new_head}~1"
    )

    # Check if diff_base is a valid commit, otherwise, it implies it's the first commit, so diff all files in new_head
    # This logic can be complex with git. For simplicity, assume get_changed_files_between_commits handles it.
    # A robust way for initial commit: `git diff-tree --no-commit-id --name-only -r <commit-hash>`
    try:
        # Attempt to see if diff_base is valid; if not, it's likely the first commit scenario
        # This is a simplification; proper git handling for initial commit diff is more nuanced.
        if diff_base == f"{new_head}~1":
            # Check if new_head has a parent
            try:
                await _run_subprocess(
                    ["git", "rev-parse", "--verify", f"{new_head}~1"],
                    cwd=pgm.project_path,
                    env=pgm.git_env(),
                )
            except subprocess.CalledProcessError:
                # new_head is the first commit, diff all its files
                stdout_initial, _ = await _run_subprocess(
                    [
                        "git",
                        "diff-tree",
                        "--no-commit-id",
                        "--name-only",
                        "-r",
                        new_head,
                    ],
                    cwd=pgm.project_path,
                    env=pgm.git_env(),
                )
                files_changed_snapshot = [
                    l.strip() for l in stdout_initial.splitlines() if l.strip()
                ]
        else:
            files_changed_snapshot = await pgm.get_changed_files_between_commits(
                diff_base, new_head
            )

    except (
        subprocess.CalledProcessError
    ):  # Fallback if diff_base is invalid (e.g. repo was empty)
        # This case implies new_head is the very first commit. Diff its content.
        stdout_initial, _ = await _run_subprocess(
            ["git", "diff-tree", "--no-commit-id", "--name-only", "-r", new_head],
            cwd=pgm.project_path,
            env=pgm.git_env(),
        )
        files_changed_snapshot = [
            l.strip() for l in stdout_initial.splitlines() if l.strip()
        ]

    tasks_snapshot = []
    for file_rel_path in files_changed_snapshot:
        abs_file = os.path.join(project_path, file_rel_path)
        dmm.remove_file_declarations(file_rel_path)  # Remove old first

        async def process_file_snapshot(file_rel_path_inner, abs_file_inner):
            if await aiofiles.os.path.exists(abs_file_inner):
                try:
                    symbols = await extract_symbols_from_file(abs_file_inner)
                    if symbols is not None and len(symbols) > 0:
                        return file_rel_path_inner, symbols
                except Exception as e_file:
                    print(f"分析{file_rel_path_inner}时失败: {e_file}")
            return file_rel_path_inner, None

        tasks_snapshot.append(process_file_snapshot(file_rel_path, abs_file))

    results_snapshot = await asyncio.gather(*tasks_snapshot)
    for file_rel_path_res, symbols_res in results_snapshot:
        if symbols_res:
            dmm.update_file_declarations(file_rel_path_res, symbols_res)

    await dmm.save_decl_map(new_head)
    changed_files_overall.extend(files_changed_snapshot)
    # Remove duplicates if any from changed_files_overall before returning
    return dmm.declaration_map, list(set(changed_files_overall))


#############################
# 调用（举例）
#############################
async def async_main():
    # Ensure these paths are correct for your test environment
    proj_path = (
        "/Users/bytedance/Projects/Hobby/CodeQA/TestProject"  # Example path, replace
    )
    git_hidden_root = (
        "/Users/bytedance/Projects/Hobby/CodeQA/TestGitHidden"  # Example path, replace
    )

    # Create dummy project and hidden git root if they don't exist for testing
    if not os.path.exists(proj_path):
        os.makedirs(proj_path)
        with open(os.path.join(proj_path, "sample.py"), "w") as f:
            f.write("def hello():\n    print('Hello')\n")
    if not os.path.exists(git_hidden_root):
        os.makedirs(git_hidden_root)

    decl_map, changed = await update_project_declaration_map(proj_path, git_hidden_root)
    print("此次变更涉及:", changed)
    if decl_map:
        print("全量symbol数量:", sum(len(v) for v in decl_map.values()))
    else:
        print("未能生成符号映射。")


if __name__ == "__main__":
    asyncio.run(async_main())
