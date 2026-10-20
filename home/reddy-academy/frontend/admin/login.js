"use strict";

(() => {
  const form = document.querySelector("#admin-login-form");
  if (!form) return;

  const error = document.querySelector("#login-error");
  const submit = form.querySelector('button[type="submit"]');
  const csrfCookie = () => document.cookie.split("; ").find((item) => item.startsWith("reddy_admin_csrf="))?.split("=").slice(1).join("=") || "";

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    error.textContent = "";
    submit.disabled = true;
    submit.querySelector("span:first-child").textContent = "Signing in…";
    try {
      const csrfResponse = await fetch("/api/admin/csrf", { credentials: "include" });
      if (!csrfResponse.ok) throw new Error("Could not initialize a secure login. Try again.");
      await csrfResponse.json();
      const csrfToken = decodeURIComponent(csrfCookie());
      const response = await fetch("/api/admin/login", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
        body: JSON.stringify({
          email: form.elements.namedItem("email").value.trim(),
          password: form.elements.namedItem("password").value
        })
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || "Sign in failed.");
      window.location.assign("/admin/dashboard");
    } catch (reason) {
      error.textContent = reason instanceof Error ? reason.message : "Sign in failed. Please try again.";
      submit.disabled = false;
      submit.querySelector("span:first-child").textContent = "Sign in";
    }
  });
})();
