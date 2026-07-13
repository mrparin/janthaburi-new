import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Durian Dashboard — สวนพรรณมณี",
  description:
    "Realtime IoT dashboard สำหรับตรวจสอบสภาพแวดล้อมในสวนทุเรียน — อุณหภูมิ ความชื้น VPD pH และพยากรณ์อากาศจาก TMD",
  keywords: ["durian", "IoT", "ทุเรียน", "สวน", "sensor", "dashboard"],
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="th">
      <head>
        <link rel="icon" href="data:," />
        <link
          rel="stylesheet"
          href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css"
        />
      </head>
      <body>{children}</body>
    </html>
  );
}
