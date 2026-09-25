import type { Metadata } from "next";
import { Tajawal } from "next/font/google";
import "./globals.css";
import Link from "next/link";
import { LayoutDashboard, FileSignature, LibrarySquare, Settings, Scale, Bell } from "lucide-react";

// استخدام خط تجوال للرصانة والفخامة
const tajawal = Tajawal({ subsets: ["arabic"], weight: ["300", "400", "500", "700"] });

export const metadata: Metadata = {
  title: "العقل القانوني | Legal Brain",
  description: "منصة الذكاء الاصطناعي القانونية المتكاملة",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ar" dir="rtl" className="dark">
      <body className={`${tajawal.className} bg-slate-950 text-slate-50 antialiased flex h-screen overflow-hidden`}>
        
        {/* القائمة الجانبية (Sidebar) */}
        <aside className="w-72 bg-slate-900 border-l border-slate-800 flex flex-col">
          <div className="h-20 flex items-center px-6 border-b border-slate-800">
            <Scale className="w-8 h-8 text-amber-500 ml-3" />
            <span className="text-2xl font-bold tracking-wide text-white">العقل القانوني</span>
          </div>
          
          <nav className="flex-1 p-4 space-y-2 overflow-y-auto">
            <Link href="/" className="flex items-center gap-3 px-4 py-3 rounded-lg text-slate-300 hover:bg-slate-800 hover:text-amber-500 transition-colors">
              <LayoutDashboard className="w-5 h-5" />
              <span className="font-medium text-lg">لوحة القيادة</span>
            </Link>
            <Link href="/workspace" className="flex items-center gap-3 px-4 py-3 rounded-lg text-slate-300 hover:bg-slate-800 hover:text-amber-500 transition-colors">
              <FileSignature className="w-5 h-5" />
              <span className="font-medium text-lg">مساحة الصياغة</span>
            </Link>
            <Link href="/library" className="flex items-center gap-3 px-4 py-3 rounded-lg text-slate-300 hover:bg-slate-800 hover:text-amber-500 transition-colors">
              <LibrarySquare className="w-5 h-5" />
              <span className="font-medium text-lg">الأرشيف والمكتبة</span>
            </Link>
          </nav>

          <div className="p-4 border-t border-slate-800">
            <Link href="/settings" className="flex items-center gap-3 px-4 py-3 rounded-lg text-slate-400 hover:bg-slate-800 transition-colors">
              <Settings className="w-5 h-5" />
              <span className="font-medium">الإعدادات</span>
            </Link>
          </div>
        </aside>

        {/* المساحة الرئيسية (Main Content) */}
        <main className="flex-1 flex flex-col h-screen overflow-hidden">
          {/* الشريط العلوي (Topbar) */}
          <header className="h-20 bg-slate-950/80 backdrop-blur-md border-b border-slate-800 flex items-center justify-between px-8 z-10">
            <div className="text-slate-400 font-medium">مرحباً بك في مكتبك الذكي</div>
            <div className="flex items-center gap-4">
              <button className="p-2 rounded-full hover:bg-slate-800 text-slate-400 transition-colors relative">
                <Bell className="w-5 h-5" />
                <span className="absolute top-1 right-1 w-2 h-2 bg-amber-500 rounded-full"></span>
              </button>
              <div className="w-10 h-10 rounded-full bg-slate-800 border border-slate-700 flex items-center justify-center text-amber-500 font-bold">
                أ.ع
              </div>
            </div>
          </header>
          
          {/* محتوى الصفحات الديناميكي */}
          <div className="flex-1 overflow-y-auto p-8">
            {children}
          </div>
        </main>
      </body>
    </html>
  );
}