"""
API 라우트 모듈
"""

from flask import Blueprint

graph_bp = Blueprint('graph', __name__)
simulation_bp = Blueprint('simulation', __name__)
report_bp = Blueprint('report', __name__)

from . import graph  # noqa: E402, F401
try:
    from . import simulation  # noqa: E402, F401
except ImportError as e:
    import logging
    logging.getLogger('mirofish').warning(f"simulation 라우트 로드 실패 (시뮬레이션 기능 비활성화): {e}")
try:
    from . import report  # noqa: E402, F401
except ImportError as e:
    import logging
    logging.getLogger('mirofish').warning(f"report 라우트 로드 실패 (보고서 기능 비활성화): {e}")
