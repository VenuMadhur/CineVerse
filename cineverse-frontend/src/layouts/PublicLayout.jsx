import { Outlet } from 'react-router-dom';
import Navbar from '../components/layout/Navbar';

export default function PublicLayout() {
  return (
    <div className="min-h-screen bg-[#0F172A]">
      <Navbar />
      <Outlet />
    </div>
  );
}
