/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        bg:     '#0d1117',
        card:   '#161b22',
        border: '#30363d',
        accent: '#58a6ff',
        up:     '#3fb950',
        down:   '#f85149',
        warn:   '#d29922',
        muted:  '#8b949e',
        text:   '#e6edf3',
      },
    },
  },
  plugins: [],
}
