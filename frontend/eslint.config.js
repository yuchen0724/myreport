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
      "no-unused-vars": "off",
      "no-console": "off",
      "vue/multi-word-component-names": "off",
      "vue/no-reserved-component-names": "off",
      "vue/no-unused-vars": "off",
    },
  },
];
