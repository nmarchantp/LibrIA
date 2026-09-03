import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'

// ESLint revisa errores y malas prácticas antes de integrar cambios al repositorio.
export default [
  // "dist" contiene archivos generados; no corresponde analizarla.
  { ignores: ['dist'] },
  {
    // Parte desde el conjunto de reglas recomendado para JavaScript.
    ...js.configs.recommended,
    // Revisa tanto módulos JavaScript normales como componentes JSX.
    files: ['**/*.{js,jsx}'],
    languageOptions: {
      ecmaVersion: 2022,
      globals: globals.browser,
      parserOptions: { ecmaVersion: 'latest', sourceType: 'module', ecmaFeatures: { jsx: true } },
    },
    // Comprueba el uso correcto de hooks y la recarga rápida de React.
    plugins: { 'react-hooks': reactHooks, 'react-refresh': reactRefresh },
    rules: {
      ...reactHooks.configs.recommended.rules,
      'react-refresh/only-export-components': ['warn', { allowConstantExport: true }],
    },
  },
]
