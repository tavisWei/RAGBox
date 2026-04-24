import { connect, waitForPageLoad } from "@/client.js";

const client = await connect();
const page = await client.page("chat-test", { viewport: { width: 1920, height: 1080 } });

// Navigate to the chat page
await page.goto("http://127.0.0.1:3005/chat");
await waitForPageLoad(page);

// Take initial screenshot
await page.screenshot({ path: "/Users/mrweij/Dev/vibe_coding/opencode/rag-reseacher/scripts/chat-initial.png" });

// Check if we need to login
const currentUrl = page.url();
console.log("Current URL:", currentUrl);

if (currentUrl.includes("/login")) {
  console.log("Need to login first");
  // Fill in login credentials
  await page.fill('input[type="email"]', "admin@example.com");
  await page.fill('input[type="password"]', "admin");
  await page.click('button[type="submit"]');
  await page.waitForTimeout(2000);
  
  // Navigate to chat page after login
  await page.goto("http://127.0.0.1:3005/chat");
  await waitForPageLoad(page);
}

// Take screenshot after login/navigation
await page.screenshot({ path: "/Users/mrweij/Dev/vibe_coding/opencode/rag-reseacher/scripts/chat-page.png" });

// Check page state
const pageTitle = await page.title();
const bodyText = await page.textContent("body");
console.log("Page title:", pageTitle);
console.log("Body text preview:", bodyText?.substring(0, 200));

// Look for the provider and model selectors
const providerSelect = await page.$('select');
console.log("Provider select found:", !!providerSelect);

// Disconnect
await client.disconnect();
