import "./globals.css";
import { Inter } from 'next/font/google';
import { AuthProvider } from "../components/contexts/AuthContext";

const inter = Inter({ subsets: ['latin'] });

export const metadata = {
  title: "CiteAI | Document Analysis",
  description: "Secure legal document analysis prototype",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="antialiased">
      <body className={inter.className}>
        <AuthProvider>
          {children}
        </AuthProvider>
      </body>
    </html>
  );
}