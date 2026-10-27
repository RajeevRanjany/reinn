import { useId } from "react";

/** Keyboard- and hover-accessible definition tooltip. */
export function InfoTip({ text }: { text: string }) {
  const id = useId();
  return (
    <span className="infotip">
      <button type="button" className="infotip-btn" aria-describedby={id} aria-label="Definition">
        i
      </button>
      <span role="tooltip" id={id} className="infotip-body">
        {text}
      </span>
    </span>
  );
}
