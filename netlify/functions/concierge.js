// netlify/functions/concierge.js
//
// This is a serverless function - it runs on Netlify's servers, not in
// the visitor's browser. That's important: it means your AI API key
// stays hidden here and is never exposed to anyone viewing the page.
//
// HOW IT WORKS:
// 1. The chat widget on the page sends the visitor's message here
// 2. This function adds context (your site's focus, affiliate link)
// 3. It calls Google's Gemini API (free tier) to generate a reply
// 4. It sends that reply back to the chat widget
//
// SETUP NEEDED:
// - Get a free Gemini API key: https://aistudio.google.com/apikey
// - In Netlify: Site settings -> Environment variables -> add
//   GEMINI_API_KEY with that key as the value
// - That's it - no key ever appears in this code or in the browser.

exports.handler = async function (event) {
  if (event.httpMethod !== "POST") {
    return { statusCode: 405, body: JSON.stringify({ error: "Method not allowed" }) };
  }

  const GEMINI_API_KEY = process.env.GEMINI_API_KEY;
  const TRAVELPAYOUTS_TOKEN = process.env.TRAVELPAYOUTS_API_TOKEN;
  const ORIGIN = "TAS"; // assumed departure city for now - Tashkent

  if (!GEMINI_API_KEY || !TRAVELPAYOUTS_TOKEN) {
    const missing = [];
    if (!GEMINI_API_KEY) missing.push("GEMINI_API_KEY");
    if (!TRAVELPAYOUTS_TOKEN) missing.push("TRAVELPAYOUTS_API_TOKEN");
    return {
      statusCode: 500,
      body: JSON.stringify({
        error: `Server is not configured yet - missing: ${missing.join(", ")}`,
      }),
    };
  }

  let userMessage;
  try {
    userMessage = JSON.parse(event.body).message;
  } catch (e) {
    return { statusCode: 400, body: JSON.stringify({ error: "Invalid request body" }) };
  }
  if (!userMessage || typeof userMessage !== "string") {
    return { statusCode: 400, body: JSON.stringify({ error: "Missing 'message' field" }) };
  }

  // STEP 1: Ask the AI for structured destination suggestions (JSON only,
  // no prose yet) so we can look up real prices for exactly these places.
  const structuredPrompt = `You are a travel concierge. Based on this visitor 
message, suggest exactly 3 flight-bookable destinations (international or 
long-haul, never local/drivable places). Respond with ONLY valid JSON, no 
other text, no markdown fences, in this exact shape:
{"destinations":[{"city":"Istanbul","iata":"IST","reason":"one short phrase why it fits"}]}
Visitor message: ${userMessage}`;

  let destinations = [];
  try {
    const aiRes = await fetch(
      `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key=${GEMINI_API_KEY}`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ contents: [{ parts: [{ text: structuredPrompt }] }] }),
      }
    );
    const aiData = await aiRes.json();
    let rawText = aiData?.candidates?.[0]?.content?.parts?.[0]?.text || "{}";
    rawText = rawText.replace(/```json|```/g, "").trim();
    const parsed = JSON.parse(rawText);
    destinations = parsed.destinations || [];
  } catch (err) {
    console.error("AI suggestion step failed:", err);
    return {
      statusCode: 502,
      body: JSON.stringify({ error: "Could not generate suggestions right now, please try again." }),
    };
  }

  if (destinations.length === 0) {
    return {
      statusCode: 200,
      body: JSON.stringify({ reply: "I couldn't find a good match for that - try describing your budget or mood a bit differently?" }),
    };
  }

  // STEP 2: For each suggested destination, fetch a REAL current price
  // from the Travelpayouts Data API - same endpoint the deal-finder script uses.
  async function fetchRealPrice(destinationIata) {
    try {
      const url = "https://api.travelpayouts.com/aviasales/v3/prices_for_dates";
      const params = new URLSearchParams({
        origin: ORIGIN,
        destination: destinationIata,
        currency: "usd",
        sorting: "price",
        direct: "false",
        one_way: "true",
        limit: "1",
      });
      const res = await fetch(`${url}?${params}`, {
        headers: { "x-access-token": TRAVELPAYOUTS_TOKEN },
      });
      const data = await res.json();
      if (data.success && data.data && data.data.length > 0) {
        const ticket = data.data[0];
        // Build a real deep link to THIS specific flight, tagged with
        // your partner marker so it still tracks as your referral.
        const PARTNER_MARKER = "747646";
        let deepLink = null;
        if (ticket.link) {
          const separator = ticket.link.includes("?") ? "&" : "?";
          deepLink = `https://www.aviasales.com${ticket.link}${separator}marker=${PARTNER_MARKER}`;
        }
        return { price: ticket.price, link: deepLink };
      }
      return { price: null, link: null };
    } catch (err) {
      console.error(`Price fetch failed for ${destinationIata}:`, err);
      return { price: null, link: null };
    }
  }

  const withPrices = await Promise.all(
    destinations.map(async (d) => {
      const result = await fetchRealPrice(d.iata);
      return { ...d, price: result.price, link: result.link };
    })
  );

  // STEP 3: Build the final reply - each destination gets its OWN
  // specific booking link (to that exact flight), not one generic link.
  const FALLBACK_LINK = "https://aviasales.tpm.lv/3zOHKKXL";
  let reply = "Here's what I found for you:\n\n";
  withPrices.forEach((d) => {
    const priceText = d.price ? `from $${d.price}` : "price currently unavailable";
    const bookLink = d.link || FALLBACK_LINK;
    reply += `${d.city} - ${priceText} - ${d.reason}\nBook this: ${bookLink}\n\n`;
  });

  return {
    statusCode: 200,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reply: reply.trim() }),
  };
};
