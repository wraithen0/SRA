import { useCallback, useEffect, useState } from "react";

export function useRevealOnScroll() {
  const [node, setNode] = useState<HTMLElement | null>(null);

  const attach = useCallback((element: HTMLElement | null) => setNode(element), []);

  useEffect(() => {
    if (!node) return;

    if (typeof IntersectionObserver === "undefined") {
      node.querySelectorAll(".reveal").forEach((el) => el.classList.add("reveal--in"));
      return;
    }

    const observed = new Set<Element>();
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            entry.target.classList.add("reveal--in");
            observed.add(entry.target);
            observer.unobserve(entry.target);
          }
        }
      },
      { rootMargin: "0px 0px -8% 0px", threshold: 0.01 }
    );

    const observe = () => {
      node.querySelectorAll(".reveal:not(.reveal--in)").forEach((el) => {
        if (!observed.has(el)) observer.observe(el);
      });
    };

    observe();
    const mutationObserver = new MutationObserver(observe);
    mutationObserver.observe(node, { childList: true, subtree: true });

    return () => {
      observer.disconnect();
      mutationObserver.disconnect();
    };
  }, [node]);

  return attach;
}