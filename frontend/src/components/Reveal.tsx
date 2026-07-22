import type { ElementType, ReactNode } from "react";
import { useReveal } from "../lib/useReveal";

export function Reveal({
  children,
  delayMs = 0,
  className = "",
  as: Component = "div",
  id,
}: {
  children: ReactNode;
  delayMs?: number;
  className?: string;
  as?: ElementType;
  id?: string;
}) {
  const { ref, visible } = useReveal<HTMLElement>();

  return (
    <Component
      ref={ref}
      id={id}
      className={`reveal ${visible ? "reveal-visible" : ""} ${className}`}
      style={{ transitionDelay: visible ? `${delayMs}ms` : "0ms" }}
    >
      {children}
    </Component>
  );
}
