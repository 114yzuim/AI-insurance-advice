import ChatApp from "@/components/chat-app";

export default async function ChatPage({
  searchParams,
}: {
  searchParams: Promise<{ init?: string }>;
}) {
  const { init } = await searchParams;
  return <ChatApp initMessage={init} />;
}
