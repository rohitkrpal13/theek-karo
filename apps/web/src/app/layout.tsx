import type { Metadata, Viewport } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Theek Karo — ठीक करो",
  description: "Citizen-powered civic reporting: report problems, watch them get fixed.",
  manifest: "/manifest.webmanifest",
  applicationName: "Theek Karo",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
  themeColor: "#157F4A",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" data-scroll-behavior="smooth" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: `(function(){var p=location.pathname.split("/")[1]||"en";document.documentElement.lang=p;})();` }} />
        <script
          dangerouslySetInnerHTML={{
            __html: `(function(){
              try{
                var m=localStorage.getItem("tk_theme")||"system";
                var d=m==="dark"||(m==="system"&&window.matchMedia("(prefers-color-scheme: dark)").matches);
                var r=d?"dark":"light";
                document.documentElement.setAttribute("data-theme",r);
                document.documentElement.style.colorScheme=r;
                document.documentElement.setAttribute("data-theme-mode",m);
              }catch(e){}
              function apply(r,m){document.documentElement.setAttribute("data-theme",r);document.documentElement.style.colorScheme=r;document.documentElement.setAttribute("data-theme-mode",m);try{localStorage.setItem("tk_theme",m)}catch(e){}}
              document.addEventListener("click",function(ev){
                var el=ev.target && ev.target.closest ? ev.target.closest("[data-theme-toggle]") : null;
                if(!el)return;
                var next=document.documentElement.getAttribute("data-theme")==="dark"?"light":"dark";
                apply(next,next);
              },true);
            })();`,
          }}
        />
      </head>
      <body className="min-h-dvh flex flex-col">{children}</body>
    </html>
  );
}