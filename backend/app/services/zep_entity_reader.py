"""
Zep 엔터티 조회 및 필터링 서비스.
Zep 그래프에서 노드를 읽어 사전 정의한 엔터티 타입에 맞는 노드를 선별한다.
"""

import time
from typing import Dict, Any, List, Optional, Set, Callable, TypeVar
from dataclasses import dataclass, field

from ..config import Config
from ..utils.logger import get_logger
from ..utils.zep_paging import fetch_all_nodes, fetch_all_edges
from ..utils.zep_client import create_zep_client

logger = get_logger('mirofish.zep_entity_reader')

# 제네릭 반환 타입
T = TypeVar('T')


@dataclass
class EntityNode:
    """엔터티 노드 데이터 구조."""
    uuid: str
    name: str
    labels: List[str]
    summary: str
    attributes: Dict[str, Any]
    # 연관 엣지 정보
    related_edges: List[Dict[str, Any]] = field(default_factory=list)
    # 연관된 다른 노드 정보
    related_nodes: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "uuid": self.uuid,
            "name": self.name,
            "labels": self.labels,
            "summary": self.summary,
            "attributes": self.attributes,
            "related_edges": self.related_edges,
            "related_nodes": self.related_nodes,
        }
    
    def get_entity_type(self) -> Optional[str]:
        """엔터티 타입을 반환한다(`Entity` 기본 라벨 제외)."""
        for label in self.labels:
            if label not in ["Entity", "Node"]:
                return label
        return None


@dataclass
class FilteredEntities:
    """필터링된 엔터티 집합."""
    entities: List[EntityNode]
    entity_types: Set[str]
    total_count: int
    filtered_count: int
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "entities": [e.to_dict() for e in self.entities],
            "entity_types": list(self.entity_types),
            "total_count": self.total_count,
            "filtered_count": self.filtered_count,
        }


class ZepEntityReader:
    """
    Zep 엔터티 조회 및 필터링 서비스.

    주요 기능:
    1. Zep 그래프에서 전체 노드 조회
    2. 사전 정의 타입에 맞는 엔터티 노드 필터링
    3. 엔터티별 연관 엣지/노드 정보 수집
    """
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or Config.ZEP_API_KEY
        if not self.api_key:
            raise ValueError("ZEP_API_KEY가 설정되지 않았습니다")
        
        self.client = create_zep_client(self.api_key)
    
    def _call_with_retry(
        self, 
        func: Callable[[], T], 
        operation_name: str,
        max_retries: int = 3,
        initial_delay: float = 2.0
    ) -> T:
        """
        재시도 로직이 포함된 Zep API 호출 래퍼.

        Args:
            func: 실행할 함수(인자 없는 lambda 또는 callable)
            operation_name: 로그용 작업 이름
            max_retries: 최대 재시도 횟수(기본 3회)
            initial_delay: 초기 지연(초)

        Returns:
            API 호출 결과
        """
        last_exception = None
        delay = initial_delay
        
        for attempt in range(max_retries):
            try:
                return func()
            except Exception as e:
                last_exception = e
                if attempt < max_retries - 1:
                    logger.warning(
                        f"Zep {operation_name} {attempt + 1}차 시도 실패: {str(e)[:100]}, "
                        f"{delay:.1f}초 후 재시도..."
                    )
                    time.sleep(delay)
                    delay *= 2  # 지수 백오프
                else:
                    logger.error(f"Zep {operation_name}가 {max_retries}회 시도 후에도 실패: {str(e)}")
        
        raise last_exception
    
    def get_all_nodes(self, graph_id: str) -> List[Dict[str, Any]]:
        """
        그래프의 전체 노드를 조회한다(페이지네이션).

        Args:
            graph_id: 그래프 ID

        Returns:
            노드 목록
        """
        logger.info(f"그래프 {graph_id}의 전체 노드 조회 중...")

        nodes = fetch_all_nodes(self.client, graph_id)

        nodes_data = []
        for node in nodes:
            nodes_data.append({
                "uuid": getattr(node, 'uuid_', None) or getattr(node, 'uuid', ''),
                "name": node.name or "",
                "labels": node.labels or [],
                "summary": node.summary or "",
                "attributes": node.attributes or {},
            })

        logger.info(f"총 {len(nodes_data)}개 노드 조회 완료")
        return nodes_data

    def get_all_edges(self, graph_id: str) -> List[Dict[str, Any]]:
        """
        그래프의 전체 엣지를 조회한다(페이지네이션).

        Args:
            graph_id: 그래프 ID

        Returns:
            엣지 목록
        """
        logger.info(f"그래프 {graph_id}의 전체 엣지 조회 중...")

        edges = fetch_all_edges(self.client, graph_id)

        edges_data = []
        for edge in edges:
            edges_data.append({
                "uuid": getattr(edge, 'uuid_', None) or getattr(edge, 'uuid', ''),
                "name": edge.name or "",
                "fact": edge.fact or "",
                "source_node_uuid": edge.source_node_uuid,
                "target_node_uuid": edge.target_node_uuid,
                "attributes": edge.attributes or {},
            })

        logger.info(f"총 {len(edges_data)}개 엣지 조회 완료")
        return edges_data
    
    def get_node_edges(self, node_uuid: str) -> List[Dict[str, Any]]:
        """
        지정 노드의 연관 엣지를 조회한다(재시도 포함).

        Args:
            node_uuid: 노드 UUID

        Returns:
            엣지 목록
        """
        try:
            # 재시도 래퍼로 Zep API 호출
            edges = self._call_with_retry(
                func=lambda: self.client.graph.node.get_entity_edges(node_uuid=node_uuid),
                operation_name=f"노드 엣지 조회(node={node_uuid[:8]}...)"
            )
            
            edges_data = []
            for edge in edges:
                edges_data.append({
                    "uuid": getattr(edge, 'uuid_', None) or getattr(edge, 'uuid', ''),
                    "name": edge.name or "",
                    "fact": edge.fact or "",
                    "source_node_uuid": edge.source_node_uuid,
                    "target_node_uuid": edge.target_node_uuid,
                    "attributes": edge.attributes or {},
                })
            
            return edges_data
        except Exception as e:
            logger.warning(f"노드 {node_uuid} 엣지 조회 실패: {str(e)}")
            return []
    
    def filter_defined_entities(
        self,
        graph_id: str,
        defined_entity_types: Optional[List[str]] = None,
        enrich_with_edges: bool = True,
        rescue_untyped: bool = False
    ) -> FilteredEntities:
        """
        사전 정의 타입에 맞는 엔터티 노드를 필터링한다.

        필터링 규칙:
        - 라벨이 `Entity`만 있는 노드는 제외
        - `Entity`/`Node` 외 라벨이 있으면 유효 엔터티로 간주

        Args:
            graph_id: 그래프 ID
            defined_entity_types: 사전 정의 엔터티 타입 목록(선택)
            enrich_with_edges: 연관 엣지 정보까지 수집할지 여부
            rescue_untyped: 커스텀 타입이 없는 노드(주로 추상 개념)를 1회 배치
                LLM 호출로 재분류해, '실제 행위자'로 판정된 것만 Person/Organization
                fallback 타입으로 구제해 에이전트에 포함한다. 개념/주제/기술/규제는
                계속 제외하므로 품질을 유지하면서 에이전트 수를 늘린다.

        Returns:
            FilteredEntities
        """
        logger.info(f"그래프 {graph_id} 엔터티 필터링 시작...")
        
        # 전체 노드 조회
        all_nodes = self.get_all_nodes(graph_id)
        total_count = len(all_nodes)
        
        # 전체 엣지 조회(후속 연관 조회용)
        all_edges = self.get_all_edges(graph_id) if enrich_with_edges else []
        
        # 노드 UUID -> 노드 데이터 매핑
        node_map = {n["uuid"]: n for n in all_nodes}
        
        # 조건 충족 엔터티 필터링
        filtered_entities = []
        entity_types_found = set()
        untyped_candidates = []  # 커스텀 타입이 없는 노드 — rescue_untyped 시 LLM 재분류 대상

        for node in all_nodes:
            labels = node.get("labels", [])

            # "Entity"/"Node" 외 라벨을 최소 1개 포함해야 함
            custom_labels = [l for l in labels if l not in ["Entity", "Node"]]

            if not custom_labels:
                # 커스텀 타입이 없는 노드: 기본 제외하되, rescue 대상으로 수집
                if rescue_untyped:
                    untyped_candidates.append(node)
                continue

            # 사전 정의 타입 지정 시 매칭 여부 확인
            if defined_entity_types:
                matching_labels = [l for l in custom_labels if l in defined_entity_types]
                if not matching_labels:
                    continue
                entity_type = matching_labels[0]
            else:
                entity_type = custom_labels[0]

            entity_types_found.add(entity_type)

            entity = EntityNode(
                uuid=node["uuid"],
                name=node["name"],
                labels=labels,
                summary=node["summary"],
                attributes=node["attributes"],
            )
            if enrich_with_edges:
                self._enrich_entity(entity, all_edges, node_map)
            filtered_entities.append(entity)

        # ===== rescue: 커스텀 타입이 없는 노드 중 '실제 행위자'만 LLM으로 구제 =====
        if rescue_untyped and untyped_candidates:
            rescued_map = self._reclassify_untyped_nodes(untyped_candidates)
            rescued_count = 0
            for node in untyped_candidates:
                assigned = rescued_map.get(node["uuid"])
                if assigned not in ("Person", "Organization"):
                    continue  # 개념/주제/기술/규제 등은 제외(SKIP)
                entity_types_found.add(assigned)
                entity = EntityNode(
                    uuid=node["uuid"],
                    name=node["name"],
                    # 구제된 노드에 fallback 타입 라벨을 부여
                    labels=list(node.get("labels", [])) + [assigned],
                    summary=node["summary"],
                    attributes=node["attributes"],
                )
                if enrich_with_edges:
                    self._enrich_entity(entity, all_edges, node_map)
                filtered_entities.append(entity)
                rescued_count += 1
            logger.info(
                f"untyped 재분류: 후보 {len(untyped_candidates)} → 행위자 구제 {rescued_count}, "
                f"개념/주제 제외 {len(untyped_candidates) - rescued_count}"
            )

        logger.info(
            f"필터링 완료: 전체 노드 {total_count}, 조건 충족 {len(filtered_entities)}, "
            f"엔터티 타입: {entity_types_found}"
        )

        return FilteredEntities(
            entities=filtered_entities,
            entity_types=entity_types_found,
            total_count=total_count,
            filtered_count=len(filtered_entities),
        )

    def _enrich_entity(
        self,
        entity: EntityNode,
        all_edges: List[Dict[str, Any]],
        node_map: Dict[str, Dict[str, Any]]
    ) -> None:
        """엔터티에 연관 엣지/노드 정보를 채운다."""
        related_edges = []
        related_node_uuids = set()

        for edge in all_edges:
            if edge["source_node_uuid"] == entity.uuid:
                related_edges.append({
                    "direction": "outgoing",
                    "edge_name": edge["name"],
                    "fact": edge["fact"],
                    "target_node_uuid": edge["target_node_uuid"],
                })
                related_node_uuids.add(edge["target_node_uuid"])
            elif edge["target_node_uuid"] == entity.uuid:
                related_edges.append({
                    "direction": "incoming",
                    "edge_name": edge["name"],
                    "fact": edge["fact"],
                    "source_node_uuid": edge["source_node_uuid"],
                })
                related_node_uuids.add(edge["source_node_uuid"])

        entity.related_edges = related_edges

        related_nodes = []
        for related_uuid in related_node_uuids:
            if related_uuid in node_map:
                related_node = node_map[related_uuid]
                related_nodes.append({
                    "uuid": related_node["uuid"],
                    "name": related_node["name"],
                    "labels": related_node["labels"],
                    "summary": related_node.get("summary", ""),
                })

        entity.related_nodes = related_nodes

    def _reclassify_untyped_nodes(self, nodes: List[Dict[str, Any]]) -> Dict[str, str]:
        """
        커스텀 타입이 없는 노드들을 1회 배치 LLM 호출로 분류한다.
        각 노드를 Person / Organization / SKIP(추상 개념·주제·기술·규제) 중 하나로 판정.

        보수적 기본값: LLM 실패/누락 시 SKIP(개념을 잘못 에이전트화하지 않음).

        Returns: {node_uuid: "Person"|"Organization"|"SKIP"}
        """
        from ..utils.llm_client import LLMClient

        # 인덱스 기반 입력(이름 중복/특수문자 안전)
        lines = []
        for i, node in enumerate(nodes):
            summary = (node.get("summary") or "").strip().replace("\n", " ")
            if len(summary) > 200:
                summary = summary[:200]
            name = node.get("name", "")
            lines.append(f"{i}. {name} — {summary}" if summary else f"{i}. {name}")
        items_block = "\n".join(lines)

        system_prompt = (
            "You classify knowledge-graph entities for a social media simulation. "
            "For each item decide whether it is a concrete social ACTOR that could post or "
            "react on social media, or an abstract concept.\n"
            "- Person: an individual human or human role (e.g. a CEO, a named expert, an analyst).\n"
            "- Organization: a company, agency, institution, media outlet, or community group.\n"
            "- SKIP: abstract topics, technologies, regulations, risks, events, or documents that "
            "cannot speak (e.g. 'security', 'EU AI Act', 'data sovereignty', 'AI', 'software').\n"
            'Return ONLY valid JSON: {"items": [{"index": <int>, "type": "Person|Organization|SKIP"}]}'
        )
        user_prompt = f"Classify each item:\n\n{items_block}"

        result_map: Dict[str, str] = {}
        try:
            client = LLMClient()
            data = client.chat_json(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.0,
                max_tokens=4000,
            )
            for item in data.get("items", []):
                try:
                    idx = int(item.get("index"))
                except (TypeError, ValueError):
                    continue
                t = item.get("type")
                if 0 <= idx < len(nodes) and t in ("Person", "Organization", "SKIP"):
                    result_map[nodes[idx]["uuid"]] = t
        except Exception as e:
            logger.warning(f"untyped 재분류 LLM 실패: {str(e)[:120]} — 전부 SKIP 처리")

        # 응답 누락분은 보수적으로 SKIP
        for node in nodes:
            result_map.setdefault(node["uuid"], "SKIP")
        return result_map
    
    def get_entity_with_context(
        self, 
        graph_id: str, 
        entity_uuid: str
    ) -> Optional[EntityNode]:
        """
        단일 엔터티와 전체 컨텍스트(엣지/연결 노드)를 조회한다.

        Args:
            graph_id: 그래프 ID
            entity_uuid: 엔터티 UUID

        Returns:
            EntityNode 또는 None
        """
        try:
            # 재시도 래퍼로 노드 조회
            node = self._call_with_retry(
                func=lambda: self.client.graph.node.get(uuid_=entity_uuid),
                operation_name=f"노드 상세 조회(uuid={entity_uuid[:8]}...)"
            )
            
            if not node:
                return None
            
            # 노드 엣지 조회
            edges = self.get_node_edges(entity_uuid)
            
            # 연관 노드 조회를 위해 전체 노드 로드
            all_nodes = self.get_all_nodes(graph_id)
            node_map = {n["uuid"]: n for n in all_nodes}
            
            # 연관 엣지/노드 정보 구성
            related_edges = []
            related_node_uuids = set()
            
            for edge in edges:
                if edge["source_node_uuid"] == entity_uuid:
                    related_edges.append({
                        "direction": "outgoing",
                        "edge_name": edge["name"],
                        "fact": edge["fact"],
                        "target_node_uuid": edge["target_node_uuid"],
                    })
                    related_node_uuids.add(edge["target_node_uuid"])
                else:
                    related_edges.append({
                        "direction": "incoming",
                        "edge_name": edge["name"],
                        "fact": edge["fact"],
                        "source_node_uuid": edge["source_node_uuid"],
                    })
                    related_node_uuids.add(edge["source_node_uuid"])
            
            # 연결된 노드 정보 채우기
            related_nodes = []
            for related_uuid in related_node_uuids:
                if related_uuid in node_map:
                    related_node = node_map[related_uuid]
                    related_nodes.append({
                        "uuid": related_node["uuid"],
                        "name": related_node["name"],
                        "labels": related_node["labels"],
                        "summary": related_node.get("summary", ""),
                    })
            
            return EntityNode(
                uuid=getattr(node, 'uuid_', None) or getattr(node, 'uuid', ''),
                name=node.name or "",
                labels=node.labels or [],
                summary=node.summary or "",
                attributes=node.attributes or {},
                related_edges=related_edges,
                related_nodes=related_nodes,
            )
            
        except Exception as e:
            logger.error(f"엔터티 {entity_uuid} 조회 실패: {str(e)}")
            return None
    
    def get_entities_by_type(
        self, 
        graph_id: str, 
        entity_type: str,
        enrich_with_edges: bool = True
    ) -> List[EntityNode]:
        """
        지정 타입의 엔터티를 모두 조회한다.

        Args:
            graph_id: 그래프 ID
            entity_type: 엔터티 타입(예: "Student", "PublicFigure")
            enrich_with_edges: 연관 엣지 정보 포함 여부

        Returns:
            엔터티 목록
        """
        result = self.filter_defined_entities(
            graph_id=graph_id,
            defined_entity_types=[entity_type],
            enrich_with_edges=enrich_with_edges
        )
        return result.entities

