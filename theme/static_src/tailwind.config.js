/**
 * This is a minimal config.
 *
 * If you need the full config, get it from here:
 * https://unpkg.com/browse/tailwindcss@latest/stubs/defaultConfig.stub.js
 */

module.exports = {
  content: [
    /**
     * HTML. Paths to Django template files that will contain Tailwind CSS classes.
     */

    /*  Templates within theme app (<tailwind_app_name>/templates), e.g. base.html. */
    "../templates/**/*.html",

    /*
     * Main templates directory of the project (BASE_DIR/templates).
     * Adjust the following line to match your project structure.
     */
    "../../templates/**/*.html",

    /*
     * Templates in other django apps (BASE_DIR/<any_app_name>/templates).
     * Adjust the following line to match your project structure.
     */
    "../../**/templates/**/*.html",

    /**
     * JS: If you use Tailwind CSS in JavaScript, uncomment the following lines and make sure
     * patterns match your project structure.
     */
    /* JS 1: Ignore any JavaScript in node_modules folder. */
    // '!../../**/node_modules',
    /* JS 2: Process all JavaScript files in the project. */
    // '../../**/*.js',

    /**
     * Python: If you use Tailwind CSS classes in Python, uncomment the following line
     * and make sure the pattern below matches your project structure.
     */
    // '../../**/*.py'
  ],
  theme: {
    extend: {
      typography: {
        DEFAULT: {
          // this is for prose class
          css: {
            p: {
              fontSize: "1.3rem",
            },
          },
        },
      },
      colors: {
        // Custom burgundy palette
        burgundy: {
          50: "#fef2f2", // Lightest burgundy tint
          100: "#fde8e8", // Very light burgundy
          200: "#fbcccc", // Light burgundy
          300: "#f89999", // Medium light burgundy
          400: "#f36666", // Medium burgundy
          500: "#e53333", // Bright burgundy
          600: "#800020", // Primary burgundy
          700: "#731d1d", // Deep burgundy
          800: "#661919", // Dark burgundy
          900: "#551414", // Darkest burgundy
        },

        // Custom green palette
        green: {
          50: "#f7faf7", // Lightest green tint
          100: "#f0f7f0", // Very light green
          200: "#ddeedd", // Light green
          300: "#c5e2c5", // Medium light green
          400: "#acd6ac", // Medium green
          500: "#9caf88", // Primary green
          600: "#8c9e7a", // Deep green
          700: "#7c8e6b", // Dark green
          800: "#6b7d5c", // Darker green
          900: "#5a6c4d", // Darkest green
        },

        // Custom yellow palette
        yellow: {
          50: "#fffef7", // Lightest yellow tint
          100: "#fffae0", // Very light yellow
          200: "#fff3b8", // Light yellow cream
          300: "#ffe985", // Medium light yellow
          400: "#ffdc4d", // Bright yellow
          500: "#ffd700", // Primary yellow (gold)
          600: "#e6c200", // Deep yellow
          700: "#cc9f00", // Golden yellow
          800: "#a67f00", // Dark golden yellow
          900: "#7a5f00", // Darkest yellow
        },

        // Custom lavender palette
        lavender: {
          50: "#faf8ff", // Lightest lavender tint
          100: "#f3efff", // Very light lavender
          200: "#e8dbff", // Light lavender
          300: "#d8c2ff", // Medium light lavender
          400: "#c7a3ff", // Medium lavender
          500: "#b586f0", // Bright lavender
          600: "#b19cd9", // Primary lavender
          700: "#9882c7", // Deep lavender
          800: "#7c6ba8", // Dark lavender
          900: "#5d5082", // Darkest lavender
        },

        // Background palette - Crisp whites
        white: {
          50: "#ffffff", // Pure white
          100: "#fefefe", // Almost white
          200: "#fdfdfd", // Off white
          300: "#fafafa", // Light gray white
          400: "#f5f5f5", // Soft white
          500: "#f0f0f0", // Medium white
          600: "#e5e5e5", // Darker white
          700: "#d4d4d4", // Light gray
          800: "#a3a3a3", // Medium gray
          900: "#525252", // Dark gray
        },

        // Secondary palette - Mediterranean blues
        mediterranean: {
          50: "#f0f9ff", // Lightest blue tint
          100: "#e0f2fe", // Very light blue
          200: "#bae6fd", // Light sky blue
          300: "#7dd3fc", // Medium light blue
          400: "#38bdf8", // Bright blue
          500: "#0ea5e9", // Medium blue
          600: "#0077be", // Primary - Mediterranean blue
          700: "#0369a1", // Deep blue
          800: "#075985", // Dark blue
          900: "#0c4a6e", // Darkest blue
        },

        // Lemon palette
        lemon: {
          50: "#fffef7", // Lightest lemon tint
          100: "#fffae0", // Very light lemon
          200: "#fff3b8", // Light lemon cream
          300: "#ffe985", // Medium light lemon
          400: "#ffdc4d", // Bright lemon
          500: "#ffd700", // Primary - lemon yellow
          600: "#e6c200", // Deep lemon
          700: "#cc9f00", // Golden lemon
          800: "#a67f00", // Dark golden yellow
          900: "#7a5f00", // Darkest lemon
        },

        // Supporting Amalfi colors
        amalfi: {
          coral: "#ff7f7f", // Coral pink buildings
          terracotta: "#e8a798", // Soft coral terracotta
          citrus: "#ffa500", // Orange citrus
          seafoam: "#4a8b8b", // Aqua sea foam
          stone: "#f5f0e8", // Limestone white
          gold: "#ffd700", // Coastal gold
        },
      },
      // Typography inspired by Italian design
      fontFamily: {
        serif: ["Crimson Text", "Libre Baskerville", "serif"],
        sans: ["Inter", "Source Sans Pro", "system-ui", "sans-serif"],
        display: ["Playfair Display", "Libre Baskerville", "serif"],
        script: ["Dancing Script", "cursive"],
      },

      // Mediterranean-inspired shadows
      boxShadow: {
        amalfi:
          "0 4px 6px -1px rgba(255, 215, 0, 0.1), 0 2px 4px -1px rgba(255, 215, 0, 0.06)",
        "amalfi-lg":
          "0 10px 15px -3px rgba(255, 215, 0, 0.1), 0 4px 6px -2px rgba(255, 215, 0, 0.05)",
        coastal:
          "0 1px 3px 0 rgba(0, 119, 190, 0.1), 0 1px 2px 0 rgba(0, 119, 190, 0.06)",
        soft: "0 4px 6px -1px rgba(177, 156, 217, 0.1), 0 2px 4px -1px rgba(177, 156, 217, 0.06)",
      },

      // Gradient combinations for Amalfi Coast flair
      backgroundImage: {
        "coastal-sunset": "linear-gradient(135deg, #ffd700 0%, #ff7f7f 100%)",
        mediterranean: "linear-gradient(135deg, #0077be 0%, #4a8b8b 100%)",
        "lemon-grove": "linear-gradient(135deg, #ffffff 0%, #ffd700 100%)",
        "lavender-coast": "linear-gradient(135deg, #b19cd9 0%, #0ea5e9 100%)",
      },
    },
  },
  plugins: [
    /**
     * '@tailwindcss/forms' is the forms plugin that provides a minimal styling
     * for forms. If you don't like it or have own styling for forms,
     * comment the line below to disable '@tailwindcss/forms'.
     */
    require("@tailwindcss/forms"),
    require("@tailwindcss/typography"),
    require("@tailwindcss/aspect-ratio"),
  ],
};
