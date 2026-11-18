// Kept apart from lib/theme.ts (a client module) so the server root layout can inline it.
export const THEME_KEY = "pet-explorer:theme";

/** Runs in <head> before first paint: stored theme, else the system preference. Prevents a wrong-theme flash. */
export const THEME_SCRIPT = `(function(){var d=document.documentElement,t;try{t=localStorage.getItem("${THEME_KEY}")}catch(e){}if(t!=="light"&&t!=="dark"){t=window.matchMedia&&matchMedia("(prefers-color-scheme: light)").matches?"light":"dark"}d.dataset.theme=t;d.style.colorScheme=t})()`;
