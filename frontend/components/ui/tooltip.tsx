"use client";

import * as TooltipPrimitive from "@radix-ui/react-tooltip";
import { Info } from "lucide-react";
import { cn } from "@/lib/utils";

export const TooltipProvider = TooltipPrimitive.Provider;
export const TooltipRoot = TooltipPrimitive.Root;
export const TooltipTrigger = TooltipPrimitive.Trigger;

export function TooltipContent({
  className,
  children,
  ...props
}: React.ComponentPropsWithoutRef<typeof TooltipPrimitive.Content>) {
  return (
    <TooltipPrimitive.Portal>
      <TooltipPrimitive.Content
        sideOffset={6}
        className={cn(
          "z-50 max-w-[260px] rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-xs text-zinc-200 shadow-xl leading-relaxed",
          className,
        )}
        {...props}
      >
        {children}
        <TooltipPrimitive.Arrow className="fill-zinc-700" />
      </TooltipPrimitive.Content>
    </TooltipPrimitive.Portal>
  );
}

export function InfoTip({ text, className }: { text: string; className?: string }) {
  return (
    <TooltipRoot delayDuration={200}>
      <TooltipTrigger asChild>
        <Info
          className={cn("inline w-3 h-3 text-zinc-600 hover:text-zinc-400 cursor-help ml-1 shrink-0", className)}
        />
      </TooltipTrigger>
      <TooltipContent>{text}</TooltipContent>
    </TooltipRoot>
  );
}
