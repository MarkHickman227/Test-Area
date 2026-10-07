(() => {
  const navToggle = document.querySelector(".nav-toggle");
  const siteNav = document.querySelector(".site-nav");

  if (navToggle && siteNav) {
    const setNavOpen = (open) => {
      siteNav.classList.toggle("is-open", open);
      navToggle.setAttribute("aria-expanded", String(open));
    };

    navToggle.addEventListener("click", (event) => {
      event.preventDefault();
      setNavOpen(!siteNav.classList.contains("is-open"));
    });

    siteNav.querySelectorAll("a").forEach((link) => {
      link.addEventListener("click", () => setNavOpen(false));
    });

    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") setNavOpen(false);
    });
  }

  const revealNodes = document.querySelectorAll(".reveal");
  if (!revealNodes.length) return;

  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    revealNodes.forEach((node) => node.classList.add("is-visible"));
    return;
  }

  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        entry.target.classList.add("is-visible");
        observer.unobserve(entry.target);
      });
    },
    { threshold: 0.18, rootMargin: "0px 0px -8% 0px" }
  );

  revealNodes.forEach((node) => observer.observe(node));
})();
