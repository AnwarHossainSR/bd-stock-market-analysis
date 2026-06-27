import daisyui from 'daisyui';

/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {},
  },
  plugins: [daisyui],
  daisyui: {
    themes: [
      {
        trader: {
          primary: '#0f766e',
          secondary: '#475569',
          accent: '#b45309',
          neutral: '#111827',
          'base-100': '#f8fafc',
          'base-200': '#eef2f7',
          'base-300': '#dbe3ed',
          info: '#2563eb',
          success: '#15803d',
          warning: '#ca8a04',
          error: '#dc2626',
        },
      },
    ],
  },
};
