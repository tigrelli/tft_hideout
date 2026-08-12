import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "About | TFT Hideout",
  description: "TFT Hideout이 무엇이고 왜 만들었는지 소개합니다.",
};

// 신규 소개 페이지(2026-08-07 PM 요청) — WBS 화면설계서에 정의되지 않은
// 페이지라 디자인 토큰(design-tokens.md)만 참고해 자유 레이아웃으로 구성.
// 데이터 fetch가 없는 정적 콘텐츠라 클라이언트 컴포넌트로 만들 필요가 없다.
export default function AboutPage() {
  return (
    <article className="mx-auto max-w-2xl">
      <h1 className="text-display text-text-primary">About</h1>

      <div className="mt-6 flex flex-col gap-5 text-body leading-relaxed text-text-primary">
        <p>
          TFT Hideout은 TFT 초보자가, 패치가 바뀔 때마다 흩어져 있는 정보를
          일일이 찾아다니지 않고도 지금 메타를 빠르게 파악할 수 있었으면
          좋겠다는 생각에서 시작된 개인 프로젝트입니다.
        </p>

        <p>
          새로운 패치가 나올 때마다 어떤 조합이 강해졌는지, 어떤 아이템을 맞춰야
          하는지 확인하려고 보통 op.gg/tft 같은 사이트를 찾아보는데, 제공하는
          정보는 정말 많고 자세하지만 그만큼 화면이 복잡해서 초보자 입장에서는
          오히려 지금 당장 필요한 것만 빠르게 확인하기 불편하다고 느꼈습니다.
          그래서 꼭 필요한 정보만 간단히 정리해서 보여주는 페이지와, 궁금한 걸
          바로 말로 물어볼 수 있는 챗봇을 함께 만들어보기로 했습니다.
        </p>

        <p>
          사이트에 올라오는 티어리스트·아이템 빌드·증강체 정보는 op.gg의
          MCP(Model Context Protocol) 연동을 통해 수집한 실전 통계와, Riot의 TFT
          Data Dragon(DDragon)에서 가져온 챔피언·아이템 정적 데이터를 조합해
          만들어집니다. 패치가 감지되면 이 두 소스를 다시 모아 정리하는 과정을
          거치기 때문에, 사이트에 보이는 정보는 항상 현재 패치 버전을 기준으로
          갱신됩니다.
        </p>

        <p>
          챗봇은 단순히 정해진 답을 출력하는 대신, 수집한 메타 문서를
          검색해(RAG) 그 안에서 근거를 찾아 답하도록 만들었습니다. 여기에 더해
          자신의 아이디를 검색하면, 그 판에서 선택한 조합이 그 시점 메타와
          얼마나 달랐는지, 아이템이 특정 챔피언에게 얼마나 집중됐는지 같은
          지표를 바탕으로 AI가 사후 분석(포스트게임 코칭) 코멘트를 만들어주는
          기능도 함께 담았습니다. 이기고 지는 것과 별개로, “이번 판에서 무엇이
          아쉬웠는지”를 스스로 되짚어보는 데 참고가 되길 바라는 마음으로 넣은
          기능입니다.
        </p>

        <p>
          TFT Hideout은 수익을 목적으로 하지 않는 비상업적 사이트입니다. 거창한
          서비스라기보다는, 저와 함께 게임을 즐기는 지인들 정도가 쓸 수 있으면
          충분하다는 생각으로 소규모로 운영하고 있습니다. 그만큼 완성도보다는
          정보를 공유하고, AI를 활용해 좀 더 편하게 게임을 이해하도록 돕는다는
          목적 자체에 무게를 두고 있습니다. 운영 중에 이상한 부분이나 잘못된
          정보를 발견하시면 언제든 알려주시면 감사하겠습니다.
        </p>
      </div>

      <hr className="my-8 border-border-default" />

      <div className="flex flex-col gap-1 text-caption text-text-secondary">
        <p>
          개발자 홈페이지:{" "}
          <a
            href="https://tigrelli.com/"
            target="_blank"
            rel="noopener noreferrer"
            className="text-text-primary hover:underline"
          >
            tigrelli.com
          </a>
        </p>
      </div>
    </article>
  );
}
