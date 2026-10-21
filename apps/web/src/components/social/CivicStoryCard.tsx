"use client"

import { useEffect, useRef, useState } from "react"
import { Button } from "@/components/ui/primitives"
import type { SocialStoryCardData } from "@/lib/types"

interface Props {
  data: SocialStoryCardData
  captionToCopy?: string
}

export function CivicStoryCard({ data, captionToCopy }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const [downloading, setDownloading] = useState(false)
  const [sharing, setSharing] = useState(false)
  const [copied, setCopied] = useState(false)

  // Draw 1080x1920 Instagram Story format
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext("2d")
    if (!ctx) return

    canvas.width = 1080
    canvas.height = 1920

    // 1. Deep Obsidian Gradient Background
    const bgGrad = ctx.createLinearGradient(0, 0, 1080, 1920)
    bgGrad.addColorStop(0, "#080c14")
    bgGrad.addColorStop(0.5, "#0f172a")
    bgGrad.addColorStop(1, "#030712")
    ctx.fillStyle = bgGrad
    ctx.fillRect(0, 0, 1080, 1920)

    // Subtle ambient glow circles
    const radGrad1 = ctx.createRadialGradient(200, 300, 10, 200, 300, 600)
    radGrad1.addColorStop(0, "rgba(249, 115, 22, 0.12)")
    radGrad1.addColorStop(1, "rgba(0, 0, 0, 0)")
    ctx.fillStyle = radGrad1
    ctx.fillRect(0, 0, 1080, 1000)

    const radGrad2 = ctx.createRadialGradient(880, 1200, 10, 880, 1200, 600)
    radGrad2.addColorStop(0, "rgba(16, 185, 129, 0.10)")
    radGrad2.addColorStop(1, "rgba(0, 0, 0, 0)")
    ctx.fillStyle = radGrad2
    ctx.fillRect(0, 800, 1080, 1120)

    // 2. Top Civic Accent Bar (Saffron, White, Green)
    const accentGrad = ctx.createLinearGradient(80, 100, 1000, 100)
    accentGrad.addColorStop(0, "#f97316")
    accentGrad.addColorStop(0.5, "#ffffff")
    accentGrad.addColorStop(1, "#10b981")
    ctx.fillStyle = accentGrad
    ctx.fillRect(80, 100, 920, 8)

    // 3. Platform Branding & Ticket Badge
    ctx.font = "bold 34px sans-serif"
    ctx.fillStyle = "#e2e8f0"
    ctx.textAlign = "left"
    ctx.fillText("THEEK KARO • CIVIC INTELLIGENCE", 80, 165)

    // Ticket Pill
    ctx.fillStyle = "#1e293b"
    roundRect(ctx, 640, 125, 360, 56, 28)
    ctx.fill()
    ctx.strokeStyle = "#38bdf8"
    ctx.lineWidth = 2
    roundRect(ctx, 640, 125, 360, 56, 28)
    ctx.stroke()

    ctx.font = "bold 26px monospace"
    ctx.fillStyle = "#38bdf8"
    ctx.textAlign = "center"
    ctx.fillText(`#${data.ticket_no}`, 820, 162)

    // 4. Alert Header Banner
    const isUrgent = data.severity.toLowerCase() === "critical" || data.severity.toLowerCase() === "high"
    ctx.fillStyle = isUrgent ? "rgba(239, 68, 68, 0.2)" : "rgba(245, 158, 11, 0.2)"
    roundRect(ctx, 80, 220, 920, 90, 20)
    ctx.fill()
    ctx.strokeStyle = isUrgent ? "#ef4444" : "#f59e0b"
    ctx.lineWidth = 3
    roundRect(ctx, 80, 220, 920, 90, 20)
    ctx.stroke()

    ctx.font = "900 36px sans-serif"
    ctx.fillStyle = isUrgent ? "#fca5a5" : "#fde68a"
    ctx.textAlign = "center"
    const alertText = isUrgent
      ? "🚨 CRITICAL CIVIC HAZARD — IMMEDIATE ACTION REQUIRED"
      : "📍 VERIFIED CIVIC OBSERVATION — ACTION REQUIRED"
    ctx.fillText(alertText, 540, 278)

    // 5. Image or Graphic Container
    const drawImageSlot = () => {
      // Content Box
      const boxY = 1100
      ctx.fillStyle = "rgba(15, 23, 42, 0.85)"
      roundRect(ctx, 80, boxY, 920, 620, 32)
      ctx.fill()
      ctx.strokeStyle = "rgba(255, 255, 255, 0.15)"
      ctx.lineWidth = 2
      roundRect(ctx, 80, boxY, 920, 620, 32)
      ctx.stroke()

      // Category + City Pill
      ctx.fillStyle = "#334155"
      roundRect(ctx, 120, boxY + 50, 480, 50, 25)
      ctx.fill()
      ctx.font = "bold 24px sans-serif"
      ctx.fillStyle = "#cbd5e1"
      ctx.textAlign = "left"
      ctx.fillText(`${data.category.toUpperCase()} • ${data.city.toUpperCase()}`, 145, boxY + 84)

      // Title
      ctx.font = "bold 52px sans-serif"
      ctx.fillStyle = "#ffffff"
      wrapText(ctx, data.title, 120, boxY + 165, 840, 64, 2)

      // Location
      ctx.font = "32px sans-serif"
      ctx.fillStyle = "#94a3b8"
      ctx.fillText("📍 " + data.address, 120, boxY + 315)

      // Demanded Authority Block
      ctx.fillStyle = "rgba(30, 41, 59, 0.9)"
      roundRect(ctx, 120, boxY + 360, 840, 190, 24)
      ctx.fill()
      ctx.strokeStyle = "#f97316"
      ctx.lineWidth = 2
      roundRect(ctx, 120, boxY + 360, 840, 190, 24)
      ctx.stroke()

      ctx.font = "bold 24px sans-serif"
      ctx.fillStyle = "#fb923c"
      ctx.fillText("🏛️ OFFICIAL ACTION DEMANDED FROM:", 155, boxY + 410)

      ctx.font = "900 40px sans-serif"
      ctx.fillStyle = "#ffffff"
      ctx.fillText(data.primary_authority_handle, 155, boxY + 465)

      ctx.font = "24px sans-serif"
      ctx.fillStyle = "#94a3b8"
      ctx.fillText(data.primary_authority_name, 155, boxY + 510)

      // 6. Footer Ledger Verification
      ctx.font = "bold 26px sans-serif"
      ctx.fillStyle = "#10b981"
      ctx.textAlign = "center"
      ctx.fillText("✓ CITIZEN VERIFIED • LOGGED ON IMMUTABLE CIVIC LEDGER", 540, 1800)

      ctx.font = "24px sans-serif"
      ctx.fillStyle = "#64748b"
      ctx.fillText("Make It Right • theekkaro.in • #TheekKaro", 540, 1845)
    }

    if (data.primary_image_url) {
      const img = new Image()
      img.crossOrigin = "anonymous"
      img.src = data.primary_image_url
      img.onload = () => {
        // Draw photo with rounded clipping
        ctx.save()
        roundRect(ctx, 80, 350, 920, 710, 28)
        ctx.clip()
        ctx.drawImage(img, 80, 350, 920, 710)
        ctx.restore()

        // Border around photo
        ctx.strokeStyle = "rgba(255, 255, 255, 0.2)"
        ctx.lineWidth = 3
        roundRect(ctx, 80, 350, 920, 710, 28)
        ctx.stroke()

        drawImageSlot()
      }
      img.onerror = () => {
        drawFallbackVisual(ctx)
        drawImageSlot()
      }
    } else {
      drawFallbackVisual(ctx)
      drawImageSlot()
    }
  }, [data])

  const handleDownload = () => {
    const canvas = canvasRef.current
    if (!canvas) return
    setDownloading(true)
    try {
      canvas.toBlob((blob) => {
        if (!blob) {
          setDownloading(false)
          return
        }
        const url = URL.createObjectURL(blob)
        const a = document.createElement("a")
        a.href = url
        a.download = `TheekKaro-${data.ticket_no}.png`
        a.click()
        URL.revokeObjectURL(url)
        setDownloading(false)
      }, "image/png")
    } catch {
      setDownloading(false)
    }
  }

  const handleShare = async () => {
    const canvas = canvasRef.current
    if (!canvas) return
    setSharing(true)

    try {
      if (captionToCopy) {
        await navigator.clipboard.writeText(captionToCopy)
        setCopied(true)
        setTimeout(() => setCopied(false), 3000)
      }

      if (navigator.share && navigator.canShare) {
        try {
          canvas.toBlob(async (blob) => {
            if (!blob) {
              handleDownload()
              return
            }
            try {
              const file = new File([blob], `TheekKaro-${data.ticket_no}.png`, { type: "image/png" })
              if (navigator.canShare({ files: [file] })) {
                await navigator.share({
                  files: [file],
                  title: `Civic Alert: ${data.title}`,
                  text: captionToCopy || `Action required on Ticket #${data.ticket_no}`,
                })
              } else {
                handleDownload()
              }
            } catch {
              handleDownload()
            }
          })
        } catch {
          handleDownload()
        }
      } else {
        handleDownload()
      }
    } catch {
      handleDownload()
    } finally {
      setSharing(false)
    }
  }

  return (
    <div className="flex flex-col items-center gap-4">
      {/* Canvas preview (scaled down via CSS for responsive viewing) */}
      <div className="relative aspect-[9/16] w-full max-w-[280px] overflow-hidden rounded-2xl border border-stone-800 shadow-2xl ring-1 ring-white/10 sm:max-w-[320px]">
        <canvas
          ref={canvasRef}
          className="h-full w-full object-contain"
          aria-label={`Civic story card for report ${data.ticket_no}`}
        />
      </div>

      <div className="flex w-full flex-wrap items-center justify-center gap-2">
        <Button
          variant="primary"
          size="sm"
          onClick={handleDownload}
          disabled={downloading}
          className="flex items-center gap-1.5"
        >
          <span>📸</span>
          <span>{downloading ? "Rendering..." : "Download Story Image (9:16)"}</span>
        </Button>

        <Button
          variant="outline"
          size="sm"
          onClick={handleShare}
          disabled={sharing}
          className="flex items-center gap-1.5"
        >
          <span>📲</span>
          <span>{copied ? "Caption Copied!" : "Share to Instagram"}</span>
        </Button>
      </div>
      <p className="text-center text-xs text-stone-400">
        1080×1920 HD Story format • High-visibility municipal tag watermark
      </p>
    </div>
  )
}

function roundRect(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  w: number,
  h: number,
  r: number,
) {
  ctx.beginPath()
  ctx.moveTo(x + r, y)
  ctx.arcTo(x + w, y, x + w, y + h, r)
  ctx.arcTo(x + w, y + h, x, y + h, r)
  ctx.arcTo(x, y + h, x, y, r)
  ctx.arcTo(x, y, x + w, y, r)
  ctx.closePath()
}

function wrapText(
  ctx: CanvasRenderingContext2D,
  text: string,
  x: number,
  y: number,
  maxWidth: number,
  lineHeight: number,
  maxLines: number,
) {
  const words = text.split(" ")
  let line = ""
  let lineCount = 0

  for (let n = 0; n < words.length; n++) {
    const testLine = line + words[n] + " "
    const metrics = ctx.measureText(testLine)
    if (metrics.width > maxWidth && n > 0) {
      ctx.fillText(line, x, y)
      line = words[n] + " "
      y += lineHeight
      lineCount++
      if (lineCount >= maxLines - 1 && n < words.length - 1) {
        ctx.fillText(line.trim() + "...", x, y)
        return
      }
    } else {
      line = testLine
    }
  }
  ctx.fillText(line, x, y)
}

function drawFallbackVisual(ctx: CanvasRenderingContext2D) {
  // Atmospheric radar graphic
  ctx.save()
  roundRect(ctx, 80, 350, 920, 710, 28)
  ctx.clip()

  const patGrad = ctx.createLinearGradient(80, 350, 1000, 1060)
  patGrad.addColorStop(0, "#1e293b")
  patGrad.addColorStop(1, "#0f172a")
  ctx.fillStyle = patGrad
  ctx.fillRect(80, 350, 920, 710)

  // Radar rings
  ctx.strokeStyle = "rgba(56, 189, 248, 0.15)"
  ctx.lineWidth = 3
  for (let r = 80; r <= 320; r += 80) {
    ctx.beginPath()
    ctx.arc(540, 705, r, 0, Math.PI * 2)
    ctx.stroke()
  }

  ctx.font = "bold 96px sans-serif"
  ctx.textAlign = "center"
  ctx.fillStyle = "#f97316"
  ctx.fillText("⚠️", 540, 720)

  ctx.font = "bold 32px sans-serif"
  ctx.fillStyle = "#94a3b8"
  ctx.fillText("CIVIC DEFECT DOCUMENTED", 540, 790)

  ctx.restore()

  ctx.strokeStyle = "rgba(255, 255, 255, 0.2)"
  ctx.lineWidth = 3
  roundRect(ctx, 80, 350, 920, 710, 28)
  ctx.stroke()
}
