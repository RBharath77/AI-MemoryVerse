import { AnimatedLoader } from "@/components/ui/animated-loader";

export default function DashboardLoading() {
  return (
    <div className="flex-1 flex items-center justify-center min-h-[70vh]">
      <AnimatedLoader size="lg" />
    </div>
  );
}
