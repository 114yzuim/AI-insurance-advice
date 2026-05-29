import TranslateApp from "@/components/translate-app";

export default async function TranslateRoute({
  searchParams,
}: {
  searchParams: Promise<{ url?: string; name?: string }>;
}) {
  const { url, name } = await searchParams;
  return <TranslateApp initPdfUrl={url ?? ""} initProductName={name ?? ""} />;
}
