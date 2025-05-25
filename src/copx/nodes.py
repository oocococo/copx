from pocketflow import AsyncNode  # Changed Node to AsyncNode
from copx.prompts.answer import ANSWER_WRITER

from copx.tools import extract_tool_calls, TOOL_NAME_LIST, invoke_tool


class AnswerFormulator(AsyncNode):  # Changed Node to AsyncNode
    async def prep_async(self, shared):
        messages = shared.get("messages")
        query = shared.get("query")
        self.params["shared"] = shared
        return query, messages

    async def exec_async(self, prep_res):
        query, messages = prep_res
        llm_client = self.params.get("shared", {}).get(
            "llm_client"
        )  # Get llm_client from shared
        if not llm_client:
            raise ValueError("llm_client not found in shared")
        prompt = ANSWER_WRITER.format(query, messages)
        response = await llm_client.call_llm(
            messages=[{"role": "user", "content": prompt}]
        )
        return response

    async def post_async(self, shared, prep_res, exec_res):
        shared["answer"] = exec_res


class CodeRetriver(AsyncNode):  # Changed Node to AsyncNode
    async def prep_async(self, shared):
        messages = shared.get("messages")
        project_path = shared.get("project_path")
        self.params["shared"] = shared
        return messages, project_path

    async def exec_async(self, inputs):
        messages, project_path = inputs
        llm_client = self.params.get("shared", {}).get(
            "llm_client"
        )  # Get llm_client from shared
        if not llm_client:
            raise ValueError("llm_client not found in shared")
        response = await llm_client.call_llm(messages=messages)

        print(f"🤖 Agent's response: {response}")

        tool_calls = extract_tool_calls(response, TOOL_NAME_LIST)
        use_tool = False
        if len(tool_calls) > 0:
            use_tool = True

        # Add project_path and declaration_map to relevant tool_calls
        declaration_map = self.params.get("shared", {}).get("declaration_map")
        if not declaration_map:
            raise ValueError("declaration_map not found in shared")

        for tool_call in tool_calls:
            if tool_call.name in ["grep_search", "view_file_content"]:
                tool_call.params["project_path"] = project_path

            if tool_call.name in ["grep_declaration_map", "view_file_declaration_map"]:
                tool_call.params["declaration_map"] = declaration_map

        formatted_tool_results_list = []
        if tool_calls:
            for call in tool_calls:
                current_tool_output_parts = []
                current_tool_output_parts.append(f"Tool Name: {call.name}")

                params_formatted = "Params:\n"
                if isinstance(call.params, dict) and call.params:
                    for arg_name, arg_value in call.params.items():
                        params_formatted += f"  {arg_name}: {str(arg_value)}\n"
                    params_formatted = params_formatted.rstrip("\n")
                elif call.params is not None:
                    params_formatted += f"  {str(call.params)}"
                else:
                    params_formatted += "  No params provided."
                current_tool_output_parts.append(params_formatted)

                try:
                    res = await invoke_tool(call)
                    current_tool_output_parts.append(
                        f"Result: {str(res)}"
                    )  # 确保结果为字符串
                except Exception as e:
                    current_tool_output_parts.append(
                        f"Error: Tool {call.name} failed: {str(e)}"
                    )

                formatted_tool_results_list.append("\n".join(current_tool_output_parts))

        # 使用分隔符连接所有工具的格式化信息
        # 如果 formatted_tool_results_list 为空 (例如没有工具调用), final_results_str 将为空字符串
        final_results_str = "\n\n--------------------\n\n".join(
            formatted_tool_results_list
        )

        return response, use_tool, final_results_str

    async def post_async(self, shared, prep_res, exec_res):
        messages, _ = prep_res
        response, use_tool, results = exec_res

        messages.append({"role": "assistant", "content": response})
        shared["messages"] = messages

        if not use_tool:
            return "answer"

        messages.append({"role": "user", "content": results})
        return "continue"
