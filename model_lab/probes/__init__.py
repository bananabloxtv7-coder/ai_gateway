# Expose the BaseProbe
from .base import BaseProbe
from .plain_chat import PlainChatProbe
from .single_tool import SingleToolCallProbe
from .streaming_tool import StreamingToolCallProbe
from .system_message import SystemMessageProbe
from .route_identity import RouteIdentityProbe
from .forced_tool import ForcedToolChoiceProbe
from .tool_result_followup import ToolResultFollowupProbe
from .sequential_tools import SequentialToolsProbe
from .parallel_tools import ParallelToolsProbe
from .tool_error_recovery import ToolErrorRecoveryProbe
from .invalid_arguments_recovery import InvalidArgumentsRecoveryProbe
from .unknown_tool_resistance import UnknownToolResistanceProbe
from .loop_termination import LoopTerminationProbe

AVAILABLE_PROBES = {
    "plain_chat": PlainChatProbe,
    "single_tool_call": SingleToolCallProbe,
    "streaming_tool_call": StreamingToolCallProbe,
    "system_message": SystemMessageProbe,
    "route_identity": RouteIdentityProbe,
    "forced_tool_choice": ForcedToolChoiceProbe,
    "tool_result_followup": ToolResultFollowupProbe,
    "sequential_tools": SequentialToolsProbe,
    "parallel_tools": ParallelToolsProbe,
    "tool_error_recovery": ToolErrorRecoveryProbe,
    "invalid_arguments_recovery": InvalidArgumentsRecoveryProbe,
    "unknown_tool_resistance": UnknownToolResistanceProbe,
    "loop_termination": LoopTerminationProbe
}
