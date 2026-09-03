import type { ButtonHTMLAttributes } from "react";
import styles from "./Button.module.css";

type Variant = "primary" | "secondary" | "warn" | "text" | "cta";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
}

/** screen-reference.dc.html のボタン様式(塗り/枠線/警告/テキストのみ)を共通化する。 */
export function Button({ variant = "secondary", className, type = "button", ...rest }: ButtonProps) {
  const classes = [styles.button, styles[variant], className].filter(Boolean).join(" ");
  return <button type={type} className={classes} {...rest} />;
}
