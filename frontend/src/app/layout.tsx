import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "锦宿 AI 视频工作台",
    template: "%s · 锦宿 AI 视频工作台",
  },
  description: "锦宿内部 AI 视频生成平台",
  icons: {
    icon: "/brand/jinxiu-logo-black.jpg",
    apple: "/brand/jinxiu-logo-black.jpg",
  },
  robots: { index: false, follow: false },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN">
      <body className="min-h-screen font-sans antialiased">{children}</body>
    </html>
  );
}
