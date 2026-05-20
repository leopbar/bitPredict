"use client";

import * as SwitchPrimitive from "@radix-ui/react-switch";
import { cn } from "@/lib/utils";

interface SwitchProps extends React.ComponentPropsWithoutRef<typeof SwitchPrimitive.Root> {
  label?: string;
}

export function Switch({ label, className, ...props }: SwitchProps) {
  return (
    <div className="flex items-center gap-2">
      <SwitchPrimitive.Root
        className={cn(
          "peer inline-flex h-5 w-9 shrink-0 cursor-pointer items-center rounded-full border-2 border-transparent",
          "transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-400",
          "disabled:cursor-not-allowed disabled:opacity-50",
          "data-[state=checked]:bg-blue-500 data-[state=unchecked]:bg-zinc-700",
          className,
        )}
        {...props}
      >
        <SwitchPrimitive.Thumb
          className={cn(
            "pointer-events-none block h-4 w-4 rounded-full bg-white shadow-lg",
            "transition-transform data-[state=checked]:translate-x-4 data-[state=unchecked]:translate-x-0",
          )}
        />
      </SwitchPrimitive.Root>
      {label && <span className="text-sm text-zinc-300">{label}</span>}
    </div>
  );
}
