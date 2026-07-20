"""
서비스 모듈
"""

from .ontology_generator import OntologyGenerator
from .text_processor import TextProcessor

try:
    from .graph_builder import GraphBuilderService
except ImportError:
    GraphBuilderService = None

try:
    from .zep_entity_reader import ZepEntityReader, EntityNode, FilteredEntities
except ImportError:
    ZepEntityReader = EntityNode = FilteredEntities = None

try:
    from .oasis_profile_generator import OasisProfileGenerator, OasisAgentProfile
except ImportError:
    OasisProfileGenerator = OasisAgentProfile = None

try:
    from .simulation_manager import SimulationManager, SimulationState, SimulationStatus
except ImportError:
    SimulationManager = SimulationState = SimulationStatus = None

try:
    from .simulation_config_generator import (
        SimulationConfigGenerator,
        SimulationParameters,
        AgentActivityConfig,
        TimeSimulationConfig,
        EventConfig,
        PlatformConfig
    )
except ImportError:
    SimulationConfigGenerator = SimulationParameters = AgentActivityConfig = None
    TimeSimulationConfig = EventConfig = PlatformConfig = None

try:
    from .simulation_runner import (
        SimulationRunner,
        SimulationRunState,
        RunnerStatus,
        AgentAction,
        RoundSummary
    )
except ImportError:
    SimulationRunner = SimulationRunState = RunnerStatus = AgentAction = RoundSummary = None

try:
    from .zep_graph_memory_updater import (
        ZepGraphMemoryUpdater,
        ZepGraphMemoryManager,
        AgentActivity
    )
except ImportError:
    ZepGraphMemoryUpdater = ZepGraphMemoryManager = AgentActivity = None

try:
    from .simulation_ipc import (
        SimulationIPCClient,
        SimulationIPCServer,
        IPCCommand,
        IPCResponse,
        CommandType,
        CommandStatus
    )
except ImportError:
    SimulationIPCClient = SimulationIPCServer = IPCCommand = None
    IPCResponse = CommandType = CommandStatus = None

__all__ = [
    'OntologyGenerator',
    'GraphBuilderService',
    'TextProcessor',
    'ZepEntityReader',
    'EntityNode',
    'FilteredEntities',
    'OasisProfileGenerator',
    'OasisAgentProfile',
    'SimulationManager',
    'SimulationState',
    'SimulationStatus',
    'SimulationConfigGenerator',
    'SimulationParameters',
    'AgentActivityConfig',
    'TimeSimulationConfig',
    'EventConfig',
    'PlatformConfig',
    'SimulationRunner',
    'SimulationRunState',
    'RunnerStatus',
    'AgentAction',
    'RoundSummary',
    'ZepGraphMemoryUpdater',
    'ZepGraphMemoryManager',
    'AgentActivity',
    'SimulationIPCClient',
    'SimulationIPCServer',
    'IPCCommand',
    'IPCResponse',
    'CommandType',
    'CommandStatus',
]
