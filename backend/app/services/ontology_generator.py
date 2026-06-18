"""
온톨로지 생성 서비스.
API 1: 문서 내용을 분석해 사회 시뮬레이션에 맞는 엔터티/관계 타입을 생성한다.
"""

import re
from typing import Dict, Any, List, Optional
from ..utils.llm_client import LLMClient


# 1차 호출: 엔터티 타입 + 문서 분석 요약 생성용 시스템 프롬프트
ENTITY_SYSTEM_PROMPT = """You design the ENTITY types of a knowledge-graph ontology for a social media opinion simulation.
Return ONLY valid JSON. Do not use markdown. Do not explain.

Entity types must be concrete actors that can speak, react, influence, or spread information.
Good entity types: people, expert roles, companies, agencies, media outlets, communities, user groups.
Bad entity types: abstract topics, emotions, trends, opinions, policies by themselves.

Return this exact JSON shape:

{
  "entity_types": [
    {
      "name": "EntityTypeName",
      "description": "English description under 60 characters",
      "attributes": [
        {"name": "attribute_name", "type": "text", "description": "English description"}
      ],
      "examples": []
    }
  ],
  "analysis_summary": "Short English summary of the document"
}

Rules:
1. Create exactly 10 entity_types.
2. The last two entity_types must be Person and Organization.
3. The first eight must be concrete types grounded in the document.
4. Entity type names must be English PascalCase.
5. Attribute names must be English snake_case.
6. Each entity type should have 1 to 2 attributes.
7. Do not use reserved attribute names: name, uuid, group_id, created_at, summary.
8. Keep every description under 60 characters.
9. Keep examples arrays empty.
10. Use compact JSON with no markdown.
"""

# 2차 호출: 관계(엣지) 타입 생성용 시스템 프롬프트
# 1차에서 확정된 엔터티 타입 목록을 컨텍스트로 받아 관계만 설계한다.
EDGE_SYSTEM_PROMPT = """You design the EDGE (relationship) types of a knowledge-graph ontology for a social media opinion simulation.
Return ONLY valid JSON. Do not use markdown. Do not explain.

You are given a fixed list of entity types. Design relationships that reflect real social
interaction: influence, mention, reaction, collaboration, conflict, reporting, advising.

Return this exact JSON shape:

{
  "edge_types": [
    {
      "name": "RELATION_NAME",
      "description": "English description under 60 characters",
      "source_targets": [
        {"source": "SourceEntityType", "target": "TargetEntityType"}
      ],
      "attributes": []
    }
  ]
}

Rules:
1. Create 6 to 8 edge_types.
2. Edge type names must be English UPPER_SNAKE_CASE.
3. Every source and target MUST be one of the provided entity type names.
4. Each edge type must have at least one source_targets pair.
5. Keep every description under 60 characters.
6. Keep attributes arrays empty.
7. Use compact JSON with no markdown.
"""


class OntologyGenerator:
    """
    온톨로지 생성기.
    문서 내용을 분석해 엔터티/관계 타입 정의를 생성한다.
    """
    
    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm_client = llm_client or LLMClient()
    
    def generate(
        self,
        document_texts: List[str],
        simulation_requirement: str,
        additional_context: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        온톨로지 정의를 생성한다.

        gemma 같은 로컬 모델은 긴 JSON을 한 번에 일관되게 출력하지 못해
        후반부(엣지)가 깨지는 문제가 있다. 그래서 2단계로 분리한다.
          1차: 엔터티 타입 + 문서 분석 요약
          2차: 확정된 엔터티 목록을 컨텍스트로 관계(엣지) 타입

        Args:
            document_texts: 문서 텍스트 목록
            simulation_requirement: 시뮬레이션 요구사항
            additional_context: 추가 컨텍스트

        Returns:
            온톨로지 정의(`entity_types`, `edge_types`, `analysis_summary`)
        """
        combined_text = self._combine_text(document_texts)

        # 1차 호출: 엔터티 타입 + 분석 요약
        entity_messages = [
            {"role": "system", "content": ENTITY_SYSTEM_PROMPT},
            {"role": "user", "content": self._build_entity_message(
                combined_text, simulation_requirement, additional_context
            )}
        ]
        entity_result = self.llm_client.chat_json(
            messages=entity_messages,
            temperature=0.3,
            max_tokens=8000
        )

        entity_types = self._process_entities(entity_result.get("entity_types", []))
        analysis_summary = entity_result.get("analysis_summary", "")
        if not isinstance(analysis_summary, str):
            analysis_summary = ""

        # 2차 호출: 엣지 타입 (확정 엔터티 목록을 컨텍스트로 전달)
        entity_names = [e["name"] for e in entity_types]
        edge_messages = [
            {"role": "system", "content": EDGE_SYSTEM_PROMPT},
            {"role": "user", "content": self._build_edge_message(
                entity_names, simulation_requirement
            )}
        ]
        edge_result = self.llm_client.chat_json(
            messages=edge_messages,
            temperature=0.3,
            max_tokens=6000
        )

        edge_types = self._process_edges(edge_result.get("edge_types", []), entity_names)

        return {
            "entity_types": entity_types,
            "edge_types": edge_types,
            "analysis_summary": analysis_summary,
        }

    # LLM에 전달할 텍스트 최대 길이(5만자)
    MAX_TEXT_LENGTH_FOR_LLM = 50000

    # Zep API 제한: 커스텀 엔터티/엣지 타입 각각 최대 10개
    MAX_ENTITY_TYPES = 10
    MAX_EDGE_TYPES = 10

    def _combine_text(self, document_texts: List[str]) -> str:
        """문서 텍스트를 병합하고 길이 제한을 적용한다."""
        combined_text = "\n\n---\n\n".join(document_texts)
        original_length = len(combined_text)

        # 5만자를 넘으면 잘라서 전달(그래프 구축 원문에는 영향 없음)
        if len(combined_text) > self.MAX_TEXT_LENGTH_FOR_LLM:
            combined_text = combined_text[:self.MAX_TEXT_LENGTH_FOR_LLM]
            combined_text += (
                f"\n\n...(원문 총 {original_length}자 중 "
                f"앞 {self.MAX_TEXT_LENGTH_FOR_LLM}자만 온톨로지 분석에 사용)..."
            )
        return combined_text

    def _build_entity_message(
        self,
        combined_text: str,
        simulation_requirement: str,
        additional_context: Optional[str]
    ) -> str:
        """1차(엔터티) 호출용 사용자 메시지를 구성한다."""
        message = f"""Simulation requirement:

{simulation_requirement}

Document text:

{combined_text}
"""
        if additional_context:
            message += f"""
Additional context:

{additional_context}
"""
        message += """
Design the entity types for a social opinion simulation from the document.
Return only valid JSON matching the system schema.
"""
        return message

    def _build_edge_message(
        self,
        entity_names: List[str],
        simulation_requirement: str
    ) -> str:
        """2차(엣지) 호출용 사용자 메시지를 구성한다."""
        names_block = "\n".join(f"- {name}" for name in entity_names)
        return f"""Simulation requirement:

{simulation_requirement}

Entity types (use these names exactly for every source and target):

{names_block}

Design the relationship (edge) types connecting these entities.
Return only valid JSON matching the system schema.
"""

    def _process_entities(self, entity_types: Any) -> List[Dict[str, Any]]:
        """엔터티 타입을 검증/정규화하고 fallback 타입을 보장한다."""
        if not isinstance(entity_types, list):
            entity_types = []

        cleaned: List[Dict[str, Any]] = []
        for entity in entity_types:
            if not isinstance(entity, dict):
                continue
            name = entity.get("name")
            # 깨진 항목 방어: 이름이 PascalCase 식별자가 아니면 폐기
            if not isinstance(name, str) or not re.match(r"^[A-Za-z][A-Za-z0-9]*$", name):
                continue
            if "attributes" not in entity or not isinstance(entity["attributes"], list):
                entity["attributes"] = []
            if "examples" not in entity or not isinstance(entity["examples"], list):
                entity["examples"] = []
            if len(entity.get("description", "")) > 100:
                entity["description"] = entity["description"][:97] + "..."
            cleaned.append(entity)

        # fallback 타입 정의
        person_fallback = {
            "name": "Person",
            "description": "Any individual person not fitting other specific person types.",
            "attributes": [
                {"name": "full_name", "type": "text", "description": "Full name of the person"},
                {"name": "role", "type": "text", "description": "Role or occupation"}
            ],
            "examples": ["ordinary citizen", "anonymous netizen"]
        }
        organization_fallback = {
            "name": "Organization",
            "description": "Any organization not fitting other specific organization types.",
            "attributes": [
                {"name": "org_name", "type": "text", "description": "Name of the organization"},
                {"name": "org_type", "type": "text", "description": "Type of organization"}
            ],
            "examples": ["small business", "community group"]
        }

        entity_names = {e["name"] for e in cleaned}
        fallbacks_to_add = []
        if "Person" not in entity_names:
            fallbacks_to_add.append(person_fallback)
        if "Organization" not in entity_names:
            fallbacks_to_add.append(organization_fallback)

        if fallbacks_to_add:
            current_count = len(cleaned)
            needed_slots = len(fallbacks_to_add)
            # 추가 후 10개를 넘으면 뒤에서 제거(앞쪽 구체 타입 우선 보존)
            if current_count + needed_slots > self.MAX_ENTITY_TYPES:
                to_remove = current_count + needed_slots - self.MAX_ENTITY_TYPES
                cleaned = cleaned[:-to_remove]
            cleaned.extend(fallbacks_to_add)

        if len(cleaned) > self.MAX_ENTITY_TYPES:
            cleaned = cleaned[:self.MAX_ENTITY_TYPES]

        return cleaned

    def _process_edges(
        self,
        edge_types: Any,
        entity_names: List[str]
    ) -> List[Dict[str, Any]]:
        """엣지 타입을 검증/정규화한다. 깨진 항목과 잘못된 참조는 폐기한다."""
        if not isinstance(edge_types, list):
            edge_types = []

        valid_names = set(entity_names)
        cleaned: List[Dict[str, Any]] = []

        for edge in edge_types:
            if not isinstance(edge, dict):
                continue
            name = edge.get("name")
            # 깨진 항목 방어: 이름이 UPPER_SNAKE_CASE 식별자가 아니면 폐기
            if not isinstance(name, str) or not re.match(r"^[A-Z][A-Z0-9_]*$", name):
                continue

            # source/target이 확정 엔터티 목록에 있는 쌍만 유지
            raw_pairs = edge.get("source_targets")
            if not isinstance(raw_pairs, list):
                raw_pairs = []
            pairs = [
                st for st in raw_pairs
                if isinstance(st, dict)
                and st.get("source") in valid_names
                and st.get("target") in valid_names
            ]
            if not pairs:
                # 유효한 관계 쌍이 하나도 없으면 폐기
                continue

            edge["source_targets"] = pairs
            if "attributes" not in edge or not isinstance(edge["attributes"], list):
                edge["attributes"] = []
            if len(edge.get("description", "")) > 100:
                edge["description"] = edge["description"][:97] + "..."
            cleaned.append(edge)

        if len(cleaned) > self.MAX_EDGE_TYPES:
            cleaned = cleaned[:self.MAX_EDGE_TYPES]

        return cleaned
    
    def generate_python_code(self, ontology: Dict[str, Any]) -> str:
        """
        온톨로지 정의를 Python 코드(ontology.py 유사 형태)로 변환한다.

        Args:
            ontology: 온톨로지 정의

        Returns:
            Python 코드 문자열
        """
        code_lines = [
            '"""',
            'Custom entity type definitions',
            'Auto-generated by MiroFish for social opinion simulation',
            '"""',
            '',
            'from pydantic import Field',
            'from zep_cloud.external_clients.ontology import EntityModel, EntityText, EdgeModel',
            '',
            '',
            '# ============== Entity Type Definitions ==============',
            '',
        ]
        
        # 엔터티 타입 코드 생성
        for entity in ontology.get("entity_types", []):
            name = entity["name"]
            desc = entity.get("description", f"A {name} entity.")
            
            code_lines.append(f'class {name}(EntityModel):')
            code_lines.append(f'    """{desc}"""')
            
            attrs = entity.get("attributes", [])
            if attrs:
                for attr in attrs:
                    attr_name = attr["name"]
                    attr_desc = attr.get("description", attr_name)
                    code_lines.append(f'    {attr_name}: EntityText = Field(')
                    code_lines.append(f'        description="{attr_desc}",')
                    code_lines.append(f'        default=None')
                    code_lines.append(f'    )')
            else:
                code_lines.append('    pass')
            
            code_lines.append('')
            code_lines.append('')
        
        code_lines.append('# ============== Relation Type Definitions ==============')
        code_lines.append('')
        
        # 관계 타입 코드 생성
        for edge in ontology.get("edge_types", []):
            name = edge["name"]
            # PascalCase 클래스명으로 변환
            class_name = ''.join(word.capitalize() for word in name.split('_'))
            desc = edge.get("description", f"A {name} relationship.")
            
            code_lines.append(f'class {class_name}(EdgeModel):')
            code_lines.append(f'    """{desc}"""')
            
            attrs = edge.get("attributes", [])
            if attrs:
                for attr in attrs:
                    attr_name = attr["name"]
                    attr_desc = attr.get("description", attr_name)
                    code_lines.append(f'    {attr_name}: EntityText = Field(')
                    code_lines.append(f'        description="{attr_desc}",')
                    code_lines.append(f'        default=None')
                    code_lines.append(f'    )')
            else:
                code_lines.append('    pass')
            
            code_lines.append('')
            code_lines.append('')
        
        # 타입 딕셔너리 생성
        code_lines.append('# ============== Type Config ==============')
        code_lines.append('')
        code_lines.append('ENTITY_TYPES = {')
        for entity in ontology.get("entity_types", []):
            name = entity["name"]
            code_lines.append(f'    "{name}": {name},')
        code_lines.append('}')
        code_lines.append('')
        code_lines.append('EDGE_TYPES = {')
        for edge in ontology.get("edge_types", []):
            name = edge["name"]
            class_name = ''.join(word.capitalize() for word in name.split('_'))
            code_lines.append(f'    "{name}": {class_name},')
        code_lines.append('}')
        code_lines.append('')
        
        # 엣지 source_targets 매핑 생성
        code_lines.append('EDGE_SOURCE_TARGETS = {')
        for edge in ontology.get("edge_types", []):
            name = edge["name"]
            source_targets = edge.get("source_targets", [])
            if source_targets:
                st_list = ', '.join([
                    f'{{"source": "{st.get("source", "Entity")}", "target": "{st.get("target", "Entity")}"}}'
                    for st in source_targets
                ])
                code_lines.append(f'    "{name}": [{st_list}],')
        code_lines.append('}')
        
        return '\n'.join(code_lines)
