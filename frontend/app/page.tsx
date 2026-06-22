import { PromptRegistryDemo } from "@/components/prompt-registry";

export default function Home() {
  return (
    <main className="relative z-10 mx-auto flex min-h-screen max-w-[1600px] flex-col px-4 py-6 sm:px-6 lg:px-8">
      <PromptRegistryDemo />
    </main>
  );
}
