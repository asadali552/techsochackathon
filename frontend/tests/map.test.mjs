import assert from "node:assert/strict";
import { after, before, test } from "node:test";
import { chromium } from "playwright";

const base = process.env.MEHFOOZ_TEST_WEB_URL || "http://localhost:5173";
let browser;
before(async () => { browser = await chromium.launch(); });
after(async () => { await browser?.close(); });

test("map separates demo data and preserves marker and advisory details", async (t) => {
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  t.after(() => page.close());
  await page.goto(base);
  await page.getByRole("heading", { name: "Safety Map", exact: true }).waitFor();
  await page.getByRole("link", { name: "OpenStreetMap", exact: true }).waitFor();
  await page.getByRole("button", { name: "Demo mode", exact: true }).click();
  await page.getByText("Layers", { exact: true }).click();
  await page.getByLabel("Incident category").selectOption("robbery");
  await page.getByText("Layers", { exact: true }).click();
  const marker = page.locator('.incident-marker[title="Robbery · Fictional demo"]');
  await marker.click();
  const details = page.getByRole("region", { name: "Incident details" });
  await details.getByText("Pending verification", { exact: true }).waitFor();
  await details.getByText(/Public pins are approximate/).waitFor();
  assert.equal(await page.locator(".incident-marker.is-selected").count(), 1);
  await details.getByRole("button", { name: "Close details" }).click();

  const polygon = page.locator(".leaflet-official-zones-pane path.leaflet-interactive").first();
  await polygon.waitFor();
  await page.getByRole("button", { name: "1 report" }).click();
  await page.getByRole("button", { name: /Fictional demo zone/ }).click();
  const zone = page.getByRole("region", { name: "Zone details" });
  await zone.getByText("Fictional area for demonstration.").waitFor();
  await zone.getByRole("button", { name: "Close details" }).click();
  await page.getByRole("button", { name: "Close reports" }).click();
  await page.getByRole("button", { name: "Demo mode", exact: true }).click();
  await marker.waitFor({ state: "detached" });
  await polygon.waitFor({ state: "detached" });
});

test("mobile map clusters reports, searches places and picks a report location", async (t) => {
  const page = await browser.newPage({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });
  t.after(() => page.close());
  await page.goto(base + "/?demo=1");
  await page.locator(".incident-cluster").first().waitFor();
  const search = page.getByRole("searchbox", { name: "Search places or reports" });
  await search.fill("Ghanta Ghar");
  await page.getByRole("button", { name: /Ghanta Ghar/ }).tap();
  assert.equal(await search.inputValue(), "Ghanta Ghar");
  await page.getByRole("navigation").getByRole("link", { name: "Report Incident" }).tap();
  await page.getByRole("button", { name: "Review report" }).tap();
  await page.getByRole("alert").getByText(/Select a category/).waitFor();
  await page.locator(".report-category").filter({ has: page.getByRole("radio", { name: "Theft", exact: true }) }).tap();
  await page.getByRole("textbox", { name: "Description", exact: true }).fill("Fictional report draft. فرضی رپورٹ۔");
  await page.getByRole("button", { name: "Choose location on map" }).tap();
  await page.getByRole("button", { name: "Use map center" }).tap();
  await page.getByText("Location selected", { exact: true }).waitFor();
  const pin = await page.locator(".leaflet-marker-pane path").boundingBox();
  const map = await page.locator(".leaflet-container").boundingBox();
  assert.ok(pin && map && Math.abs(pin.x + pin.width / 2 - (map.x + map.width / 2)) <= 2);
  assert.ok(Math.abs(pin.y + pin.height / 2 - (map.y + map.height / 2)) <= 2);
  await page.getByRole("button", { name: "Search location", exact: true }).tap();
  await page.getByRole("searchbox", { name: "Search locations", exact: true }).fill("Ghanta");
  await page.getByRole("button", { name: /Ghanta Ghar/ }).tap();
  await page.getByRole("button", { name: "Review report" }).tap();
  await page.getByText("Sign in required", { exact: true }).waitFor();
  assert.equal(await page.getByRole("button", { name: "Submit incident" }).count(), 0);
  await page.getByText("Ghanta Ghar", { exact: true }).waitFor();
  await page.getByRole("button", { name: "Edit report" }).tap();
  assert.equal(await page.getByRole("textbox", { name: "Description", exact: true }).inputValue(), "Fictional report draft. فرضی رپورٹ۔");
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
});

async function surfacePixels(image) {
  return image.evaluate(async (element) => {
    await element.decode();
    const canvas = document.createElement("canvas");
    canvas.width = element.naturalWidth;
    canvas.height = element.naturalHeight;
    const context = canvas.getContext("2d");
    context.drawImage(element, 0, 0);
    const { data } = context.getImageData(0, 0, canvas.width, canvas.height);
    const alpha = new Set();
    let transparent = 0, green = 0, warm = 0, red = 0;
    for (let i = 0; i < data.length; i += 4) {
      const [r, g, b, a] = data.subarray(i, i + 4);
      alpha.add(a);
      if (a === 0) transparent++;
      if (a < 35) continue;
      if (g > r + 25 && g > b + 20) green++;
      if (r > g + 30 && g > b + 28) warm++;
      if (r > g + 70 && g < 65) red++;
    }
    return { transparent, green, warm, red, opacityLevels: alpha.size };
  });
}

test("reported-risk raster blends eligible scores and keeps unsupported space clear", async (t) => {
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  t.after(() => page.close());
  await page.goto(base + "/?demo=1");
  const heat = page.locator(".leaflet-heatmap-cells-pane");
  const surface = heat.locator("img.risk-surface");
  const pixels = await surfacePixels(surface);
  assert.ok(pixels.transparent > 0 && pixels.green > 0 && pixels.warm > 0 && pixels.red > 0, JSON.stringify(pixels));
  assert.ok(pixels.opacityLevels > 20);
  assert.equal(await heat.locator("path").count(), 0);

  await page.getByRole("button", { name: "Inspect center cell" }).click();
  const details = page.getByRole("region", { name: "Heatmap cell details" });
  await details.getByText("Reported risk", { exact: true }).waitFor();
  await details.getByRole("button", { name: "Close heatmap details" }).click();
  const [night] = await Promise.all([
    page.waitForResponse((response) => response.url().includes("period=night") && response.ok()),
    page.getByLabel("Historical period").selectOption("night"),
  ]);
  const { data: nightData } = await night.json();
  assert.equal(nightData.period, "night");
  assert.ok(nightData.cells.features.some((cell) => cell.properties.security.band === "red"));
  const updated = page.locator(".heatmap-status time");
  const before = await updated.getAttribute("datetime");
  await page.getByRole("button", { name: "Refresh heatmap" }).click();
  await page.waitForFunction((previous) => {
    const current = document.querySelector(".heatmap-status time")?.getAttribute("datetime");
    return current && current > previous;
  }, before);
  await page.getByLabel("Historical period").selectOption("full_day");
  await page.getByText("Layers", { exact: true }).click();
  await page.getByLabel("Reported risk layer").selectOption("road_hazards");
  await page.getByText("Layers", { exact: true }).click();
  await page.getByLabel("Reported risk legend").getByText("Road hazards", { exact: true }).waitFor();
  await page.locator(".leaflet-official-zones-pane path.leaflet-interactive").first().waitFor();
  await page.getByText("Layers", { exact: true }).click();
  await page.getByRole("checkbox", { name: "Heatmap", exact: true }).uncheck();
  await surface.waitFor({ state: "detached" });
});

test("heatmap uses the canvas renderer when WebGL is unavailable", async (t) => {
  const page = await browser.newPage({ viewport: { width: 1024, height: 768 } });
  t.after(() => page.close());
  await page.addInitScript(() => {
    const original = HTMLCanvasElement.prototype.getContext;
    HTMLCanvasElement.prototype.getContext = function (kind, ...options) {
      return kind === "webgl" ? null : original.call(this, kind, ...options);
    };
  });
  await page.goto(base + "/?demo=1");
  const pixels = await surfacePixels(page.locator("img.risk-surface--canvas"));
  assert.ok(pixels.transparent > 0 && pixels.green > 0 && pixels.red > 0, JSON.stringify(pixels));
});

test("activity uses a distinct density surface with the same historical data", async (t) => {
  const page = await browser.newPage({ viewport: { width: 1024, height: 768 } });
  t.after(() => page.close());
  await page.goto(base + "/?demo=1");
  await page.locator("img.risk-surface--risk").waitFor();
  assert.deepEqual(await page.locator(".risk-scale span").allTextContents(), ["0–20", "21–40", "41–60", "61–80", "81–100"]);
  let requests = 0;
  page.on("request", (request) => { if (request.url().includes("/api/heatmap?")) requests++; });
  await page.getByRole("button", { name: "Activity", exact: true }).click();
  const activity = page.locator("img.risk-surface--activity");
  await activity.waitFor();
  const pixels = await surfacePixels(activity);
  assert.equal(pixels.green + pixels.warm + pixels.red, 0);
  assert.ok(pixels.opacityLevels > 20);
  await page.getByText("Concentration of eligible reports.", { exact: true }).waitFor();
  assert.equal(requests, 0);
  await page.getByRole("button", { name: "Zoom in" }).click();
  await activity.waitFor();
});

test("planner picks, searches and swaps places, selects routes, and handles provider errors", async (t) => {
  const page = await browser.newPage({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });
  t.after(() => page.close());
  const cors = { "access-control-allow-origin": "*", "access-control-allow-methods": "POST, GET, OPTIONS", "access-control-allow-headers": "content-type" };
  const pointA = [71.467842, 30.198803], pointB = [71.4446, 30.1804];
  const routes = [0, 1].map((i) => ({
    id: `route-${i}`, geometry: { type: "LineString", coordinates: [pointA, [71.454 + i * .004, 30.19], pointB] },
    distance_m: 3700 + i * 200, duration_s: 330 + i * 100,
  }));
  const evidence = { report_count: 0, score: null, band: "grey", coverage: "unavailable", category_counts: {}, latest_report_at: null };
  let releaseRouting;
  const routing = new Promise((resolve) => { releaseRouting = resolve; });
  await page.route("**/api/routes?**", async (route) => {
    await routing;
    return route.fulfill({ json: { data: { routes, provider: "OSRM" }, error: null }, headers: cors });
  });
  await page.route("**/api/routes/compare", (route) => route.request().method() === "OPTIONS"
    ? route.fulfill({ status: 204, headers: cors })
    : route.fulfill({ json: { data: {
      routes: routes.map((line) => ({ ...line, security: evidence, road_hazards: evidence, official_zones: [], trade_offs: [] })),
      mode: "demo", corridor_m: 250, evidence_window_days: 30,
    }, error: null }, headers: cors }));
  await page.goto(base + "/?demo=1#planner");
  const startInput = page.getByRole("textbox", { name: "Start", exact: true });
  const destinationInput = page.getByRole("textbox", { name: "Destination", exact: true });
  await page.getByRole("button", { name: "Pick start on map" }).tap();
  await page.getByRole("button", { name: "Use map center" }).tap();
  await page.waitForFunction(() => /^30\.\d+, 71\.\d+$/.test(document.querySelector("#journey-origin").value));
  await startInput.fill("Ghan");
  await startInput.press("ArrowDown");
  await page.getByRole("button", { name: /Ghanta Ghar/ }).press("Enter");
  await destinationInput.fill("Cant");
  await page.getByRole("button", { name: /Multan Cantonment Railway Station/ }).tap();
  await page.getByRole("button", { name: "Swap locations" }).tap();
  assert.equal(await startInput.inputValue(), "Multan Cantonment Railway Station");
  assert.equal(await destinationInput.inputValue(), "Ghanta Ghar");
  await page.getByRole("button", { name: "Swap locations" }).tap();
  await page.getByRole("button", { name: "Departure time" }).tap();
  await page.getByLabel(/Departure date and time/).fill("2026-11-11T22:00");
  await page.getByRole("button", { name: "Use now" }).tap();
  await page.getByRole("button", { name: "Find routes" }).tap();
  try {
    await page.getByText("Finding driving routes…", { exact: true }).waitFor();
  } finally {
    releaseRouting();
  }
  await page.getByText("2 routes available", { exact: true }).waitFor();
  await page.locator(".leaflet-journey-routes-pane path.route-selected").waitFor();
  await page.getByRole("button", { name: /Route 2/ }).tap();
  assert.equal(await page.getByRole("button", { name: /Route 2/ }).getAttribute("aria-pressed"), "true");
  await page.locator(".route-pin[title='Route destination']").waitFor();
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
  await page.waitForFunction(() => {
    const sheet = document.querySelector(".journey-panel");
    const pins = [...document.querySelectorAll(".route-pin")];
    return pins.length === 2 && pins.every((pin) => pin.getBoundingClientRect().bottom < sheet.getBoundingClientRect().top);
  });
  await page.getByRole("button", { name: "Clear trip" }).tap();
  assert.equal(await startInput.inputValue(), "");
  assert.equal(await destinationInput.inputValue(), "");
  await page.locator("path.route-selected").waitFor({ state: "detached" });
  await page.getByRole("button", { name: "Use sample trip" }).tap();
  await page.unroute("**/api/routes?**");
  await page.route("**/api/routes?**", (route) => route.fulfill({
    status: 503, headers: cors, json: { data: null, error: { code: "routing_unavailable", message: "Routing provider unavailable." } },
  }));
  await page.getByRole("button", { name: "Find routes" }).tap();
  await page.getByRole("alert").getByText("Routing provider unavailable.", { exact: true }).waitFor();
  await page.unroute("**/api/routes?**");
  await page.route("**/api/routes?**", (route) => route.fulfill({ json: { data: { routes: [], provider: "OSRM" }, error: null }, headers: cors }));
  await page.getByRole("button", { name: "Find routes" }).tap();
  await page.getByText(/No driving route was found/).waitFor();
});

test("assistant shows grounded area and cell evidence, then clears context", async (t) => {
  const page = await browser.newPage({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });
  t.after(() => page.close());
  await page.goto(base + "/?demo=1#assistant");
  const prompt = page.getByRole("button", { name: "Is Gulgasht safe to visit tonight?" });
  const chat = "**/api/ai/chat";
  const { promise: release, resolve } = Promise.withResolvers();
  await page.route(chat, async (route) => { await release; await route.abort(); }, { times: 1 });
  try {
    await prompt.tap();
    await page.getByText("Checking available travel data…").waitFor();
  } finally {
    resolve();
  }
  await page.getByRole("button", { name: "Retry question" }).tap();
  await page.getByText(/Location resolved to Gulgasht Colony/).waitFor();
  await page.getByText(/Fictional demo/).first().waitFor();
  await page.getByText("1,500 m area · Night", { exact: false }).waitFor();
  await page.getByRole("link", { name: "Close assistant" }).tap();
  await page.waitForURL("**#map");
  await page.getByRole("link", { name: "AI Assistant" }).tap();
  await page.getByText("1,500 m area · Night", { exact: false }).waitFor();
  const input = page.getByRole("textbox", { name: "Ask about travel safety" });
  await input.fill("What about tomorrow morning?");
  await input.press("Enter");
  await page.getByText("1,500 m area · Morning", { exact: false }).waitFor();
  await page.getByRole("button", { name: "Show location on map" }).last().tap();
  await page.waitForURL("**#map");
  await page.getByRole("button", { name: "Inspect center cell" }).tap();
  await page.getByRole("button", { name: "Ask about this cell" }).tap();
  await input.fill("Explain this heatmap cell");
  await page.getByRole("button", { name: "Send question" }).tap();
  await page.getByText(/m heatmap cell · Morning/).waitFor();
  await page.getByRole("button", { name: "Clear conversation" }).tap();
  await page.getByText("Where are you headed?").waitFor();
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
});

test("tablet map keeps advisories visible during a heatmap outage and can retry", async (t) => {
  const page = await browser.newPage({ viewport: { width: 820, height: 1180 }, hasTouch: true });
  t.after(() => page.close());
  const pattern = "**/api/heatmap?**";
  await page.route(pattern, (route) => route.abort());
  await page.goto(base + "/?demo=1#map");
  await page.locator(".leaflet-official-zones-pane path").first().waitFor();
  await page.getByText(/API could not be reached/).waitFor();
  assert.equal(await page.locator("img.risk-surface--risk").count(), 0);
  await page.unroute(pattern);
  await page.getByRole("button", { name: "Refresh heatmap" }).click();
  await page.locator("img.risk-surface--risk").waitFor();
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
});
