import "../../src/components/canal.css";
import CanalDashboard from "@/src/components/canal-dashboard";
import Providers from "@/src/components/providers";

export default function CanalPage() {
  return (
    <Providers>
      <CanalDashboard />
    </Providers>
  );
}
