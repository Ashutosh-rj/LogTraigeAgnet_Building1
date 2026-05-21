import { cn } from "@/lib/utils";

const styles = {
  critical: "bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-200",
  high: "bg-orange-100 text-orange-700 dark:bg-orange-950 dark:text-orange-200",
  medium: "bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-200",
  low: "bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-200",
  open: "bg-rose-100 text-rose-700 dark:bg-rose-950 dark:text-rose-200",
  investigating: "bg-blue-100 text-blue-700 dark:bg-blue-950 dark:text-blue-200",
  resolved: "bg-green-100 text-green-700 dark:bg-green-950 dark:text-green-200",
  closed: "bg-slate-100 text-slate-700 dark:bg-slate-900 dark:text-slate-200",
  neutral: "bg-muted text-muted-foreground"
} as const;

export function Badge({
  tone = "neutral",
  children,
  className
}: {
  tone?: keyof typeof styles;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <span className={cn("inline-flex rounded-md px-2 py-1 text-xs font-medium", styles[tone], className)}>
      {children}
    </span>
  );
}

