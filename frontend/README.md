# frontend

Next.js(App Router) + Tailwind CSS v4. Cloudflare Workers([assets] 전용, 정적 export)에 배포한다.

## 개발

```
npm install
npm run dev      # http://localhost:3000
npm run build    # 정적 export → out/
npm run lint
npm run format:check
npm test         # Vitest + React Testing Library
```

## 디자인 토큰

`src/app/globals.css`의 `@theme` 블록이 `/docs/reference/design-tokens.md`를 원본으로 한다.
토큰 값이 바뀌면 두 파일을 함께 갱신한다(FE-01 테스트가 두 값의 일치를 검증한다).

## 배포

`output: "export"`로 빌드하면 `out/`에 정적 파일이 생성되고, `wrangler.toml`의
`[assets] directory`가 이를 가리킨다. Cloudflare 대시보드의 빌드 명령을
`cd frontend && npm install && npm run build`, 출력 디렉터리를 `frontend/out`으로
설정해야 한다(SET-07 당시엔 `index.html` 더미 파일을 그대로 서빙했으나 FE-01부터는
빌드 스텝이 필요 — PM 확인 필요).
