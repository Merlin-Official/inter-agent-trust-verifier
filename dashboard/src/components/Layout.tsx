import React from 'react';
import { NavLink } from 'react-router-dom';
import {
    ShieldCheck,
    Activity,
    Users,
    FileText,
    Settings,
} from 'lucide-react';
import clsx from 'clsx';

export const Layout: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    return (
        <div className="flex h-screen overflow-hidden bg-dark-bg text-dark-text">

            {/* Sidebar */}
            <aside className="w-64 flex-shrink-0 bg-dark-card border-r border-dark-border flex flex-col">

                <div className="h-16 flex items-center px-6 border-b border-dark-border select-none">
                    <ShieldCheck className="w-8 h-8 text-accent mr-3" />

                    <h1 className="text-xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-blue-400 to-emerald-400 leading-tight">
                        Trust<br />Verifier
                    </h1>
                </div>

                <nav className="flex-1 px-4 py-6 flex flex-col gap-2 overflow-y-auto">

                    <NavItem
                        to="/"
                        icon={<Activity size={20} />}
                        label="Overview"
                    />

                    <NavItem
                        to="/agents"
                        icon={<Users size={20} />}
                        label="Agent Registry"
                    />

                    <NavItem
                        to="/audit"
                        icon={<FileText size={20} />}
                        label="Audit Trail"
                    />

                    <NavItem
                        to="/simulation"
                        icon={<ShieldCheck size={20} />}
                        label="Simulations"
                    />

                </nav>

                <div className="p-4 border-t border-dark-border">
                    <div className="flex items-center text-sm text-dark-muted px-2 cursor-pointer hover:text-white transition-colors">
                        <Settings size={16} className="mr-3" />
                        <span>Settings</span>
                    </div>
                </div>

            </aside>

            {/* Main Content */}
            <main className="flex-1 overflow-y-auto w-full relative">
                <div className="max-w-7xl mx-auto p-8">
                    {children}
                </div>
            </main>

        </div>
    );
};


interface NavItemProps {
    to: string;
    icon: React.ReactNode;
    label: string;
}

const NavItem: React.FC<NavItemProps> = ({ to, icon, label }) => {
    return (
        <NavLink
            to={to}
            className={({ isActive }) =>
                clsx(
                    "flex items-center px-4 py-3 rounded-lg font-medium transition-all duration-200",
                    isActive
                        ? "bg-accent/10 text-accent border border-accent/20"
                        : "text-dark-muted hover:bg-white/5 hover:text-white"
                )
            }
        >
            <span className="mr-3 flex items-center">
                {icon}
            </span>

            {label}
        </NavLink>
    );
};