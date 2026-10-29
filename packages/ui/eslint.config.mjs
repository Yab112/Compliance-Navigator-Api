// Same rules as the apps that compile this code; a package has no pages directory to check links against
import apps from "../../web/eslint.config.mjs";

const config = [...apps, { rules: { "@next/next/no-html-link-for-pages": "off" } }];

export default config;
