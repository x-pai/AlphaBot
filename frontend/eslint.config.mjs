import { dirname } from "path";
import { fileURLToPath } from "url";
import { FlatCompat } from "@eslint/eslintrc";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const compat = new FlatCompat({
  baseDirectory: __dirname,
});

const eslintConfig = [
  ...compat.extends("next/core-web-vitals", "next/typescript"),
  {
    rules: {
      // 将未使用的变量和导入转为警告
      "@typescript-eslint/no-unused-vars": "warn",
      
      // 关闭未转义引号的错误
      "react/no-unescaped-entities": "off",
      
      // 将 any 类型问题转为警告
      "@typescript-eslint/no-explicit-any": "warn",
      
      // 将空接口问题转为警告
      "@typescript-eslint/no-empty-object-type": "warn",
      
      // 将 useEffect 依赖项问题转为警告
      "react-hooks/exhaustive-deps": "error",
      
      // 将 img 元素使用问题转为警告
      // "@next/next/no-img-element": "warn"
    }
  }
];

export default eslintConfig;
