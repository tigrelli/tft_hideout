# design-tokens.md — 디자인 토큰 경량 참조본

> 원본: 디자인가이드 v1.0 3~6장, 화면설계서 v1.2. 원본 버전이 바뀔 때만 이 파일을 갱신한다.
> 이 파일은 FE-* TASK 시작 시 원본 .docx 대신 먼저 참조한다 (CLAUDE.md 2장). Figma 실제 프레임 대조가 필요하면 Figma MCP(`get_design_context`/`get_screenshot`) 사용.

## 컬러

| 토큰 | HEX | 용도 |
|---|---|---|
| Primary(Brand) | `#4059D9` | GNB 로고 강조·챗봇 헤더·CTA·챗봇 플로팅 버튼 |
| Accent(Carry) | `#E59933` | 캐리 챔피언 강조 보더(2px) |
| Text/Primary | `#1A1A1A` | 제목, 본문 강조 |
| Text/Secondary | `#666666` | 본문 설명, 메타 정보 |
| Text/Tertiary | `#8C8C8C` | placeholder, 비활성, "승률 표시 안함" |
| Text/On-Brand | `#FFFFFF` | 브랜드 컬러 배경 위 텍스트 |
| Surface/Card | `#FFFFFF` | 카드, 챗봇 패널, 드롭다운 배경 |
| Surface/Page | `#F7F7F7` | 페이지 배경, 필터 바 배경 |
| Surface/User Bubble | `#E5E8FF` | 챗봇 사용자 발화 말풍선 |
| Border/Default | `#D9D9D9` | 카드·챗봇 패널 보더, 구분선 |
| Border/Input | `#CCCCCC` | 드롭다운·인풋 보더 |

### 티어 배지 (권장안, 미확정 항목 — 변경 시 PM 확인)

S=`#E5B93D`(골드) · A=`#8C6FE0`(퍼플) · B=`#4C9BE0`(블루) · C=`#8C8C8C`(그레이)

## 타이포그래피

서체: Inter(라틴/숫자), 국문은 시스템 기본 폰트 폴백.

| 스타일 | 크기/굵기 | 용도 |
|---|---|---|
| Display | 22px Bold | 상세 화면 타이틀 |
| H1/Logo | 20px Bold | GNB 로고 |
| H2/Section | 16~18px Bold | 섹션 제목 |
| Label/Badge | 11~12px SemiBold | 티어 배지, 제안 칩 |
| Body | 13~14px Regular | 본문, 카드 설명 |
| Caption | 12px Regular | 근거 텍스트, 보조 설명 |

## 스페이싱 · 반경 · 그리드

- 스페이싱 스케일(4px 배수): 4·8·12·16·20·24·32·40px. 카드 내부 패딩 16px, 카드 그리드 gap 16px, 데스크톱 좌우 여백 40px
- 반경: 카드 8px · 배지/칩 4px · 버튼/드롭다운 6px · 챗봇 말풍선 10px · 챗봇 플로팅 버튼 50%(56×56px)
- 카탈로그 그리드: 데스크톱 3~4열(gap 16px) · 태블릿 2열(gap 16px) · 모바일 1열 스택(gap 12px)

## 브레이크포인트 반응형 전환 규칙

| 컴포넌트 | 데스크톱/태블릿 | 모바일 |
|---|---|---|
| GNB | 가로 내비게이션 바 | 햄버거 → 전체화면 드로어 |
| 카탈로그 그리드 | 3~4열(태블릿 2열) | 1열 카드 스택 |
| 챗봇 위젯 | 우하단 플로팅(360×505, radius 10) | 하단 고정 바 → 탭 시 전체화면 바텀시트 |
| 필터 UI | Dropdown | Bottom Sheet |

## 주요 컴포넌트 스펙

- **버튼(Primary)**: 배경 `#4059D9`, 텍스트 `#FFFFFF`, radius 6px, 패딩 20/12px
- **카드**: 배경 `#FFFFFF`, 보더 `#D9D9D9` 1px, radius 8px, 패딩 16px, 전체 클릭 영역
- **챗봇 위젯**: collapsed 56×56px 원형 / expanded 360×480~505px, 헤더 배경 `#4059D9`+흰 텍스트, 사용자 말풍선 `#E5E8FF` radius 10px 우측정렬, 봇 답변 좌측정렬 + 근거 텍스트(Caption, `#666666`)

## 미확정 항목 (변경 전 PM 확인 필수)

티어 배지 색상 최종 채택, 캐리/서브 챔피언 구분 표시 방식(보더는 확정: `#E59933` 2px), 챔피언/아이템 아이콘 실제 이미지(현재 그레이박스 placeholder), 분석 리포트 그래프/타임라인 세부 톤.
