"""实时事件与持久化历史共用的状态归约器（reducer）。"""
import copy


def empty():
    return {"messages": [], "tools": {}, "status": "idle"}


def reduce(state, event):
    kind = event["type"]
    if kind == "message_end":
        state["messages"].append(event["message"])
    elif kind == "task_start":
        state["status"] = "running"
    elif kind == "tool_execution_start":
        state["tools"][event["toolCallId"]] = {
            "name": event["name"], "arguments": event["arguments"],
            "status": "running", "output": None, "isError": None,
        }
    elif kind == "tool_execution_update":
        state["tools"][event["toolCallId"]]["progress"] = event["output"]
    elif kind == "tool_execution_end":
        tool = state["tools"][event["toolCallId"]]
        tool.update(status="failed" if event["isError"] else "succeeded",
                    output=event["output"], isError=event["isError"])
        tool.pop("progress", None)
    elif kind == "task_end":
        state["status"] = event["status"]
    return state


def stable(state, disconnected=False):
    result = copy.deepcopy(state)
    # 临时进度不是恢复来源；失去后端后，running 只能解释为结果未知。
    for tool in result["tools"].values():
        tool.pop("progress", None)
        if disconnected and tool["status"] == "running":
            tool["status"] = "interrupted"
    if disconnected and result["status"] == "running":
        result["status"] = "interrupted"
    return result
