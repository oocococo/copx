import argparse
import json
from pathlib import Path
import importlib
import asyncio
import aiofiles

from tree_sitter import Language, Parser

# --- Configuration and Language Loading ---
DEFAULT_CONFIG_DIR = Path(__file__).parent / "configs"


class ConfigurationError(Exception):
    pass


class TreeSitterLanguageNotFoundError(Exception):
    pass


async def load_language_config(file_extension, config_dir=DEFAULT_CONFIG_DIR):
    """Loads the language-specific configuration file asynchronously."""
    config_file = config_dir / f"{file_extension.lstrip('.')}.json"
    if not await asyncio.to_thread(config_file.exists):
        raise ConfigurationError(f"Configuration file not found: {config_file}")
    try:
        async with aiofiles.open(config_file, "r", encoding="utf-8") as f:
            content = await f.read()
            return await asyncio.to_thread(json.loads, content)
    except json.JSONDecodeError as e:
        raise ConfigurationError(f"Error decoding JSON from {config_file}: {e}")
    except Exception as e:
        raise ConfigurationError(f"Error loading config {config_file}: {e}")


async def get_tree_sitter_language(lang_module_name, lang_config=None):
    """
    Loads the tree-sitter Language object for the given language asynchronously.
    Assumes tree-sitter bindings (e.g., tree_sitter_go) are pip installed.
    Uses lang_config to find an optional 'language_accessor_name'.
    """
    if lang_config is None:
        lang_config = {}

    try:
        module = await asyncio.to_thread(importlib.import_module, lang_module_name)
        accessor_name = lang_config.get("language_accessor_name", "language")
        
        if not hasattr(module, accessor_name):
            raise TreeSitterLanguageNotFoundError(
                f"Language accessor '{accessor_name}' not found in module '{lang_module_name}'."
            )
            
        language_attribute = getattr(module, accessor_name)
        
        if callable(language_attribute):
            # If the accessor points to a callable function (e.g., module.language()),
            # call it to get the underlying language pointer and construct the Language object.
            return await asyncio.to_thread(Language, language_attribute())
        elif isinstance(language_attribute, Language):
            # If the accessor points directly to an already constructed Language object instance.
            return language_attribute
        else:
            # If the accessor is neither a callable returning a pointer, nor a Language instance.
            raise TreeSitterLanguageNotFoundError(
                f"Language accessor '{accessor_name}' in module '{lang_module_name}' "
                f"is not a callable function returning a language pointer, nor an instance of tree_sitter.Language. "
                f"Found type: {type(language_attribute).__name__}."
            )

    except ImportError:
        raise TreeSitterLanguageNotFoundError(
            f"Tree-sitter language module '{lang_module_name}' not found. "
            f"Please install it (e.g., 'pip install {lang_module_name.replace('_', '-')}')"
        )
    except Exception as e:
        raise TreeSitterLanguageNotFoundError(
            f"Error loading language '{lang_module_name}': {e}. "
            "Ensure the language grammar is correctly built or installed."
        )


# --- Symbol Extraction Logic ---
async def extract_symbols_from_code(root_node, code_bytes, lang_config):
    """
    Extracts symbols from the code based on the language configuration asynchronously.
    Returns a list of dictionaries, each representing a symbol.
    """
    symbols = []
    extraction_rules = lang_config.get("extraction_rules", [])

    def get_name_and_identifier_line(name_node, code_bytes):
        if name_node:
            name_text = code_bytes[name_node.start_byte : name_node.end_byte].decode(
                "utf-8", errors="ignore"
            )
            identifier_line = name_node.start_point[0] + 1  # 0-indexed to 1-indexed
            return name_text, identifier_line
        return None, None

    async def walk(node):
        for rule in extraction_rules:
            if node.type == rule["node_type"]:
                # Simple case: direct name extraction
                if "name_field" in rule:
                    name_node = node.child_by_field_name(rule["name_field"])
                    name, identifier_line = await asyncio.to_thread(get_name_and_identifier_line, name_node, code_bytes)
                    if name and identifier_line:
                        declaration_start_line = node.start_point[0] + 1
                        declaration_end_line = node.end_point[0] + 1
                        symbols.append(
                            {
                                "name": name,
                                "type": rule["symbol_type"],
                                "identifier_line": identifier_line,
                                "declaration_start_line": declaration_start_line,
                                "declaration_end_line": declaration_end_line,
                            }
                        )

                # Complex case: process children based on further rules
                elif "process_children" in rule:
                    pc_rule = rule["process_children"]
                    child_types_to_process = pc_rule["child_node_type"]
                    if isinstance(child_types_to_process, str):
                        child_types_to_process = [child_types_to_process]

                    for child in node.children:
                        if child.type in child_types_to_process:
                            declaration_start_line = child.start_point[0] + 1
                            declaration_end_line = child.end_point[0] + 1
                            name_node = (
                                child.child_by_field_name(
                                    pc_rule["name_field_on_child"]
                                )
                                if "name_field_on_child" in pc_rule
                                else None
                            )

                            if "type_determining_field_on_child" in pc_rule:
                                type_det_node = child.child_by_field_name(
                                    pc_rule["type_determining_field_on_child"]
                                )
                                symbol_cat = pc_rule["default_symbol_type"]
                                if (
                                    type_det_node
                                    and type_det_node.type in pc_rule["type_mapping"]
                                ):
                                    symbol_cat = pc_rule["type_mapping"][
                                        type_det_node.type
                                    ]

                                name, identifier_line = await asyncio.to_thread(get_name_and_identifier_line, name_node, code_bytes)
                                if name and identifier_line:
                                    symbols.append(
                                        {
                                            "name": name,
                                            "type": symbol_cat,
                                            "identifier_line": identifier_line,
                                            "declaration_start_line": declaration_start_line,
                                            "declaration_end_line": declaration_end_line,
                                        }
                                    )
                            elif (
                                "type_mapping" in pc_rule
                                and "type_determining_field_on_child" not in pc_rule
                            ):
                                symbol_cat = pc_rule["type_mapping"].get(child.type)
                                name, identifier_line = await asyncio.to_thread(get_name_and_identifier_line, name_node, code_bytes)
                                if name and identifier_line and symbol_cat:
                                    symbols.append(
                                        {
                                            "name": name,
                                            "type": symbol_cat,
                                            "identifier_line": identifier_line,
                                            "declaration_start_line": declaration_start_line,
                                            "declaration_end_line": declaration_end_line,
                                        }
                                    )
                            elif "name_node_is_list_on_child" in pc_rule:
                                names_list_holder_node = child.child_by_field_name(
                                    pc_rule["name_node_is_list_on_child"]
                                )
                                if names_list_holder_node:
                                    for (
                                        var_identifier_node
                                    ) in names_list_holder_node.children:
                                        if (
                                            var_identifier_node.type == "identifier"
                                        ):
                                            name, identifier_line = (
                                                await asyncio.to_thread(get_name_and_identifier_line, var_identifier_node, code_bytes)
                                            )
                                            if name and identifier_line:
                                                symbols.append(
                                                    {
                                                        "name": name,
                                                        "type": pc_rule["symbol_type"],
                                                        "identifier_line": identifier_line,
                                                        "declaration_start_line": declaration_start_line,
                                                        "declaration_end_line": declaration_end_line,
                                                    }
                                                )
                            elif (
                                "name_field_on_child" in pc_rule
                                and "symbol_type" in pc_rule
                            ):
                                name, identifier_line = await asyncio.to_thread(get_name_and_identifier_line, name_node, code_bytes)
                                if name and identifier_line:
                                    symbols.append(
                                        {
                                            "name": name,
                                            "type": pc_rule["symbol_type"],
                                            "identifier_line": identifier_line,
                                            "declaration_start_line": declaration_start_line,
                                            "declaration_end_line": declaration_end_line,
                                        }
                                    )
        for child_node in node.children:
            await walk(child_node)

    await walk(root_node)
    unique_symbols = []
    seen_symbols = set()
    # Sorting can be CPU intensive for large lists, consider if it's critical path
    sorted_symbols = await asyncio.to_thread(
        sorted,
        symbols,
        key=lambda x: (
            x["declaration_start_line"],
            x["identifier_line"],
            x["name"],
            x["type"],
        ),
    )
    for s in sorted_symbols:
        symbol_tuple = (
            s["name"],
            s["type"],
            s["identifier_line"],
            s["declaration_start_line"],
            s["declaration_end_line"],
        )
        if symbol_tuple not in seen_symbols:
            unique_symbols.append(s)
            seen_symbols.add(symbol_tuple)

    return unique_symbols


async def extract_symbols_from_file(filepath, config_dir=DEFAULT_CONFIG_DIR):
    filepath = Path(filepath)
    if not await asyncio.to_thread(filepath.exists) or not await asyncio.to_thread(filepath.is_file):
        print(f"Error: File not found or is not a file: {filepath}")
        return

    file_extension = filepath.suffix
    if not file_extension:
        print(f"Error: Could not determine file extension for {filepath}")
        return

    try:
        lang_config = await load_language_config(file_extension, Path(config_dir))
        ts_lang_module_name = lang_config.get("tree_sitter_module")
        if not ts_lang_module_name:
            raise ConfigurationError("'tree_sitter_module' not specified in config.")

        TS_LANGUAGE = await get_tree_sitter_language(ts_lang_module_name, lang_config)

        async with aiofiles.open(filepath, "rb") as f:
            code_bytes = await f.read()

        parser = await asyncio.to_thread(Parser, TS_LANGUAGE)
        tree = await asyncio.to_thread(parser.parse, code_bytes)
        root_node = tree.root_node

        symbols = await extract_symbols_from_code(root_node, code_bytes, lang_config)

        if not symbols:
            print(f"No symbols found in {filepath} based on the current configuration.")
            return

        return symbols

    except ConfigurationError as e:
        print(f"Configuration Error: {e}")
    except TreeSitterLanguageNotFoundError as e:
        print(f"Language Loading Error: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        import traceback
        traceback.print_exc()


async def main():
    parser_arg = argparse.ArgumentParser(
        description="Extracts symbols (functions, structs, etc.) from source code files."
    )
    parser_arg.add_argument("filename", help="Path to the source code file")
    parser_arg.add_argument(
        "--config-dir",
        default=str(DEFAULT_CONFIG_DIR),
        help=f"Directory containing language configuration JSON files (default: {DEFAULT_CONFIG_DIR})",
    )
    args = parser_arg.parse_args()

    filepath = Path(args.filename)
    # File existence checks are now in extract_symbols_from_file

    symbols = await extract_symbols_from_file(filepath, args.config_dir)

    if symbols:
        print(f"Symbols found in {filepath}:")
        # Potentially CPU-bound, but usually small lists for printing
        max_name_len = await asyncio.to_thread(max, (len(s["name"]) for s in symbols), default=10)
        max_type_len = await asyncio.to_thread(max, (len(s["type"]) for s in symbols), default=10)

        header = f"{'Name':<{max_name_len}} | {'Type':<{max_type_len}} | ID Line | Decl Start | Decl End"
        print(header)
        print("-" * len(header))
        for sym in symbols:
            print(
                f"{sym['name']:<{max_name_len}} | {sym['type']:<{max_type_len}} | {str(sym['identifier_line']):<7} | {str(sym['declaration_start_line']):<10} | {str(sym['declaration_end_line']):<8}"
            )

if __name__ == "__main__":
    asyncio.run(main())
