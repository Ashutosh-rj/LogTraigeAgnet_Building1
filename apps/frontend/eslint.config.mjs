import js from "@eslint/js";
import nextPlugin from "@next/eslint-plugin-next";
import tseslint from "typescript-eslint";

export default [
  js.configs.recommended,
  ...tseslint.configs.recommended,

  {
    ignores: [
      ".next/**",
      "node_modules/**",
      "coverage/**",
      "next-env.d.ts"
    ]
  },

  {
    plugins: {
      "@next/next": nextPlugin
    },

    rules: {
      ...nextPlugin.configs["core-web-vitals"].rules,

      "no-undef": "off",

      "@typescript-eslint/no-unused-vars": [
        "warn",
        {
          argsIgnorePattern: "^_"
        }
      ]
    }
  }
];