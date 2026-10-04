import "./globals.css";

export const metadata = {
  title: "zkLeash",
  description: "Decisions from the zkLeash orchestrator",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
