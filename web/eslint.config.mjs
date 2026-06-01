import nextCoreWebVitals from "eslint-config-next/core-web-vitals";
import nextTypeScript from "eslint-config-next/typescript";

const eslintConfig = [
  ...nextCoreWebVitals,
  ...nextTypeScript,
  {
    rules: {
      // Advisory perf hint from react-hooks v6 (bundled with Next 16). Our flagged
      // uses are intentional: external-store sync (useMediaQuery) and animation
      // drivers (useCountUp). Keep visible as a warning rather than failing lint;
      // revisit as a tracked useSyncExternalStore refactor.
      "react-hooks/set-state-in-effect": "warn",
      // Pages-Router-era rule; this is an App Router project (no `pages/` dir). It
      // misfires on the intentional hard-reload <a href="/"> in app/error.tsx,
      // where a soft <Link> would not reliably reset the errored render tree.
      "@next/next/no-html-link-for-pages": "off",
    },
  },
];

export default eslintConfig;
