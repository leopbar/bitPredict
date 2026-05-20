"use client";

import * as SliderPrimitive from "@radix-ui/react-slider";
import { cn } from "@/lib/utils";

interface SliderProps extends React.ComponentPropsWithoutRef<typeof SliderPrimitive.Root> {
  label?: string;
  valueDisplay?: string;
}

export function Slider({ label, valueDisplay, className, ...props }: SliderProps) {
  return (
    <div className="space-y-2">
      {label && (
        <div className="flex justify-between items-center">
          <span className="text-sm text-zinc-400">{label}</span>
          {valueDisplay && (
            <span className="text-sm text-zinc-100 font-medium">{valueDisplay}</span>
          )}
        </div>
      )}
      <SliderPrimitive.Root
        className={cn(
          "relative flex w-full touch-none select-none items-center",
          className,
        )}
        {...props}
      >
        <SliderPrimitive.Track className="relative h-1.5 w-full grow overflow-hidden rounded-full bg-zinc-700">
          <SliderPrimitive.Range className="absolute h-full bg-blue-500" />
        </SliderPrimitive.Track>
        <SliderPrimitive.Thumb className="block h-4 w-4 rounded-full border-2 border-blue-500 bg-[#0A0A0B] shadow focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 disabled:pointer-events-none disabled:opacity-50 transition-transform hover:scale-110" />
      </SliderPrimitive.Root>
    </div>
  );
}
