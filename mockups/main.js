/**
 * Airbnb Investment Intelligence — main.js
 *
 * Responsibilities:
 *  - Tab navigation
 *  - Sidebar slider readouts
 *  - Chart.js initialisation (bubble + price distribution)
 *  - Tooltip keyboard accessibility
 */

(function () {
  "use strict";

  /* ──────────────────────────────────────────
     Utility helpers
  ────────────────────────────────────────── */

  /**
   * Returns true when the user's OS is set to dark mode.
   * @returns {boolean}
   */
  function prefersDark() {
    return window.matchMedia("(prefers-color-scheme: dark)").matches;
  }

  /**
   * Shared chart axis colours derived from the current colour scheme.
   * @returns {{ grid: string, tick: string }}
   */
  function chartColours() {
    return {
      grid: prefersDark() ? "rgba(255,255,255,0.07)" : "rgba(0,0,0,0.06)",
      tick: prefersDark() ? "#aaa" : "#888",
    };
  }

  /* ──────────────────────────────────────────
     Tab navigation
  ────────────────────────────────────────── */

  /**
   * Wire up the four navigation tabs.
   * Switches the visible page section and updates aria-selected.
   */
  function initTabs() {
    const tabs = document.querySelectorAll(".nav-tab");
    const pages = document.querySelectorAll(".page");

    tabs.forEach(function (tab) {
      tab.addEventListener("click", function () {
        const target = tab.dataset.tab;

        /* Deactivate all tabs and hide all pages */
        tabs.forEach(function (t) {
          t.classList.remove("active");
          t.setAttribute("aria-selected", "false");
        });

        pages.forEach(function (p) {
          p.classList.remove("active");
          p.hidden = true;
        });

        /* Activate the selected tab and page */
        tab.classList.add("active");
        tab.setAttribute("aria-selected", "true");

        var page = document.getElementById("page-" + target);
        if (page) {
          page.classList.add("active");
          page.hidden = false;
        }
      });
    });
  }

  /* ──────────────────────────────────────────
     Sidebar slider readouts
  ────────────────────────────────────────── */

  /**
   * Attach live-readout handlers to the three range sliders.
   */
  function initSliders() {
    var priceSlider = document.getElementById("priceSlider");
    var priceVal = document.getElementById("priceVal");
    if (priceSlider && priceVal) {
      priceSlider.addEventListener("input", function () {
        priceVal.textContent = "up to £" + priceSlider.value;
        priceSlider.setAttribute("aria-valuetext", "up to £" + priceSlider.value);
      });
    }

    var reviewSlider = document.getElementById("reviewSlider");
    var reviewVal = document.getElementById("reviewVal");
    if (reviewSlider && reviewVal) {
      reviewSlider.addEventListener("input", function () {
        reviewVal.textContent = "≥ " + reviewSlider.value;
        reviewSlider.setAttribute("aria-valuetext", "≥ " + reviewSlider.value);
      });
    }

    var availSlider = document.getElementById("availSlider");
    var availVal = document.getElementById("availVal");
    if (availSlider && availVal) {
      availSlider.addEventListener("input", function () {
        availVal.textContent = "≥ " + availSlider.value + " days";
        availSlider.setAttribute("aria-valuetext", "≥ " + availSlider.value + " days");
      });
    }
  }

  /* ──────────────────────────────────────────
     Tooltip keyboard accessibility
  ────────────────────────────────────────── */

  /**
   * Allow the tooltip icon to be toggled with Enter / Space when focused,
   * supplementing the CSS :hover behaviour.
   */
  function initTooltips() {
    var icons = document.querySelectorAll(".tooltip-icon");
    icons.forEach(function (icon) {
      icon.addEventListener("keydown", function (e) {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          var wrap = icon.closest(".tooltip-wrap");
          if (!wrap) return;
          var box = wrap.querySelector(".tooltip-box");
          if (!box) return;
          var isVisible = box.style.display === "block";
          box.style.display = isVisible ? "" : "block";
        }
      });

      /* Close on Escape */
      icon.addEventListener("keydown", function (e) {
        if (e.key === "Escape") {
          var wrap = icon.closest(".tooltip-wrap");
          if (!wrap) return;
          var box = wrap.querySelector(".tooltip-box");
          if (box) box.style.display = "";
        }
      });
    });

    /* Close tooltip when focus leaves the wrap entirely */
    document.addEventListener("focusin", function (e) {
      document.querySelectorAll(".tooltip-wrap").forEach(function (wrap) {
        if (!wrap.contains(e.target)) {
          var box = wrap.querySelector(".tooltip-box");
          if (box) box.style.display = "";
        }
      });
    });
  }

  /* ──────────────────────────────────────────
     Bubble chart — revenue vs occupancy
  ────────────────────────────────────────── */

  /**
   * Render the property-type bubble chart on the overview page.
   */
  function initBubbleChart() {
    var canvas = document.getElementById("bubbleChart");
    if (!canvas) return;

    var c = chartColours();

    new Chart(canvas, {
      type: "bubble",
      data: {
        datasets: [
          {
            label: "Entire home/apt",
            data: [{ x: 62, y: 33500, r: 22 }],
            backgroundColor: "rgba(216,90,48,0.75)",
            borderColor: "#993C1D",
            borderWidth: 1,
          },
          {
            label: "Private room",
            data: [{ x: 55, y: 13700, r: 14 }],
            backgroundColor: "rgba(136,135,128,0.75)",
            borderColor: "#5F5E5A",
            borderWidth: 1,
          },
          {
            label: "Shared room",
            data: [{ x: 47, y: 6500, r: 6 }],
            backgroundColor: "rgba(180,178,169,0.75)",
            borderColor: "#888780",
            borderWidth: 1,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        layout: { padding: { top: 16, right: 16, bottom: 8, left: 8 } },
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: function (ctx) {
                return (
                  ctx.dataset.label +
                  " — Occupancy: " +
                  ctx.raw.x +
                  "%, Revenue: £" +
                  Math.round(ctx.raw.y / 1000) +
                  "k"
                );
              },
            },
          },
        },
        scales: {
          x: {
            title: {
              display: true,
              text: "Occupancy proxy (%)",
              color: c.tick,
              font: { size: 11 },
            },
            min: 35,
            max: 75,
            grid: { color: c.grid },
            ticks: {
              color: c.tick,
              font: { size: 11 },
              callback: function (v) {
                return v + "%";
              },
            },
          },
          y: {
            title: {
              display: true,
              text: "Est. annual revenue (£)",
              color: c.tick,
              font: { size: 11 },
            },
            min: 0,
            max: 40000,
            grid: { color: c.grid },
            ticks: {
              color: c.tick,
              font: { size: 11 },
              callback: function (v) {
                return "£" + Math.round(v / 1000) + "k";
              },
            },
          },
        },
      },
    });
  }

  /* ──────────────────────────────────────────
     Price distribution histogram
  ────────────────────────────────────────── */

  /**
   * Render the nightly price distribution bar chart on the overview page.
   */
  function initPriceDistChart() {
    var canvas = document.getElementById("priceDistChart");
    if (!canvas) return;

    var c = chartColours();

    new Chart(canvas, {
      type: "bar",
      data: {
        labels: [
          "<£40",
          "£40–60",
          "£60–80",
          "£80–100",
          "£100–120",
          "£120–160",
          "£160–200",
          "£200–300",
          "£300+",
        ],
        datasets: [
          {
            label: "Listings",
            data: [4200, 9800, 15400, 18200, 16800, 12300, 7100, 4200, 1800],
            backgroundColor: "#D85A30",
            borderRadius: 2,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: function (ctx) {
                return (
                  ctx.dataset.label +
                  ": " +
                  ctx.raw.toLocaleString()
                );
              },
            },
          },
        },
        scales: {
          x: {
            grid: { display: false },
            ticks: {
              color: c.tick,
              font: { size: 11 },
              maxRotation: 35,
              autoSkip: false,
            },
          },
          y: {
            grid: { color: c.grid },
            ticks: {
              color: c.tick,
              font: { size: 11 },
              callback: function (v) {
                return Math.round(v / 1000) + "k";
              },
            },
          },
        },
      },
    });
  }

  /* ──────────────────────────────────────────
     Placeholder button handlers
  ────────────────────────────────────────── */

  /**
   * Attach console-logged stubs to the action buttons so they are
   * ready to wire to a real API endpoint in the Streamlit backend.
   */
  function initButtonHandlers() {
    var regenBtn = document.getElementById("regenBtn");
    if (regenBtn) {
      regenBtn.addEventListener("click", function () {
        console.info(
          "[Airbnb Intel] Regenerate clicked — connect to AI recommendations endpoint."
        );
      });
    }

    var analyseBtn = document.getElementById("analyseBtn");
    if (analyseBtn) {
      analyseBtn.addEventListener("click", function () {
        console.info(
          "[Airbnb Intel] Analyse reviews clicked — connect to review analysis endpoint."
        );
      });
    }
  }

  /* ──────────────────────────────────────────
     Boot
  ────────────────────────────────────────── */

  /**
   * Initialise all modules once the DOM is ready.
   */
  function init() {
    initTabs();
    initSliders();
    initTooltips();
    initBubbleChart();
    initPriceDistChart();
    initButtonHandlers();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
