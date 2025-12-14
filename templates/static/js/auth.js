const API_BASE = "http://127.0.0.1:8000/accounts";

document.getElementById("registerForm")?.addEventListener("submit", async e => {
  e.preventDefault();

  const data = {
    username: username.value,
    email: email.value,
    password: password.value,
    password2: password2.value
  };

  const res = await fetch(`${API_BASE}/api/register/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data)
  });

  if (res.ok) {
    alert("Registration successful. Please login.");
    window.location.href = "/accounts/login/";
  } else {
    alert("Registration failed");
  }
});

document.getElementById("loginForm")?.addEventListener("submit", async e => {
  e.preventDefault();

  const res = await fetch(`${API_BASE}/api/token/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      email: email.value,
      password: password.value
    })
  });

  const data = await res.json();

  if (res.ok) {
    localStorage.setItem("access", data.access);
    localStorage.setItem("refresh", data.refresh);
    window.location.href = "/dashboard/";
  } else {
    alert("Login failed");
  }
});
