import pluginVue from "eslint-plugin-vue";

export default [
  {
    ignores: ["dist/**", "node_modules/**"],
  },
  ...pluginVue.configs["flat/essential"],
  {
    files: ["src/**/*.{js,vue}"],
    languageOptions: {
      ecmaVersion: "latest",
      sourceType: "module",
      globals: {
        window: "readonly",
        document: "readonly",
        console: "readonly",
number: "readonly",
        setTimeout: "readonly",
        clearTimeout: "readonly",
        setInterval: "readonly",
        clearInterval: "readonly",
        fetch: "readonly",
        URLSearchParams: "readonly",
        alert: "readonly",
        confirm: "readonly",
      },
    },
    rules: {
      "no-unused-vars": ["warn", { argsIgnorePattern: "^_" }],
      "no-console": "off",
    },
  },
];
