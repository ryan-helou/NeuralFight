import { Outlet } from 'react-router-dom';
import { TooltipProvider } from '@/components/ui/tooltip';
import Navbar from './Navbar';

export default function Layout() {
  return (
    <TooltipProvider>
      <div className="dark min-h-screen bg-background text-foreground">
        <Navbar />
        <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
          <Outlet />
        </main>
      </div>
    </TooltipProvider>
  );
}
