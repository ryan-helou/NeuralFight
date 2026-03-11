import { Link, useLocation } from 'react-router-dom';

const navItems = [
  { path: '/', label: 'Events' },
  { path: '/upsets', label: 'Upset Alerts' },
];

export default function Navbar() {
  const location = useLocation();

  return (
    <nav className="border-b border-gray-800 bg-gray-900/80 backdrop-blur-sm sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 h-16 flex items-center justify-between">
        <Link to="/" className="text-xl font-bold text-white tracking-tight">
          Neural<span className="text-red-500">Fight</span>
        </Link>
        <div className="flex gap-6">
          {navItems.map((item) => (
            <Link
              key={item.path}
              to={item.path}
              className={`text-sm font-medium transition-colors ${
                location.pathname === item.path
                  ? 'text-red-400'
                  : 'text-gray-400 hover:text-white'
              }`}
            >
              {item.label}
            </Link>
          ))}
        </div>
      </div>
    </nav>
  );
}
