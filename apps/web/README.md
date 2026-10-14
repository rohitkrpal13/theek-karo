This is a [Next.js](https://nextjs.org) project bootstrapped with [`create-next-app`](https://nextjs.org/docs/app/api-reference/cli/create-next-app).

## Getting Started

First, run the development server:

```bash
npm run dev
# or
yarn dev
# or
pnpm dev
# or
bun dev
```

Open [http://localhost:3000](http://localhost:3000) with your browser to see the result.

## Report evidence uploads

Attaching evidence requires signing in. Reports can still be submitted without files. The form accepts up to five JPEG, PNG, or WebP images, up to 8 MB each.

For local development, the upload CSP allows the default MinIO origin at `http://127.0.0.1:9000`. If the API uses a different HTTP object-storage origin, set `NEXT_PUBLIC_MEDIA_UPLOAD_ORIGIN` to that origin before starting Next.js. HTTPS upload origins are already allowed.

## Institution discovery

Explore suggestions and name searches use institutions registered in Theek Karo. Nearby search requests browser location only after the user selects **Use my current location**; coordinates are sent to Theek Karo's `/gis/map/nearby` API and are not sent to an external place-search provider. An empty result means the registered, coordinate-bearing directory has no matching institution data; it is not filled with estimated or synthetic places. See [`docs/PROVENANCE.md`](../../docs/PROVENANCE.md) for dataset licensing and coverage status.

You can start editing the page by modifying `app/page.tsx`. The page auto-updates as you edit the file.

This project uses [`next/font`](https://nextjs.org/docs/app/building-your-application/optimizing/fonts) to automatically optimize and load [Geist](https://vercel.com/font), a new font family for Vercel.

## Learn More

To learn more about Next.js, take a look at the following resources:

- [Next.js Documentation](https://nextjs.org/docs) - learn about Next.js features and API.
- [Learn Next.js](https://nextjs.org/learn) - an interactive Next.js tutorial.

You can check out [the Next.js GitHub repository](https://github.com/vercel/next.js) - your feedback and contributions are welcome!

## Deploy on Vercel

The easiest way to deploy your Next.js app is to use the [Vercel Platform](https://vercel.com/new?utm_medium=default-template&filter=next.js&utm_source=create-next-app&utm_campaign=create-next-app-readme) from the creators of Next.js.

Check out our [Next.js deployment documentation](https://nextjs.org/docs/app/building-your-application/deploying) for more details.
