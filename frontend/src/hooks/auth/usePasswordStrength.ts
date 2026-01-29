/**
 * Password strength checking utility hook.
 * Provides password strength scoring and suggestions.
 */

// ============================================================================
// Types
// ============================================================================

export interface PasswordStrength {
  score: number; // 0-4
  label: "Very Weak" | "Weak" | "Fair" | "Strong" | "Very Strong";
  suggestions: string[];
  color: string;
}

// ============================================================================
// Password Strength Checker
// ============================================================================

export function checkPasswordStrength(password: string): PasswordStrength {
  let score = 0;
  const suggestions: string[] = [];

  if (password.length === 0) {
    return {
      score: 0,
      label: "Very Weak",
      suggestions: ["Enter a password"],
      color: "bg-gray-200",
    };
  }

  // Length checks
  if (password.length >= 8) score++;
  else suggestions.push("Use at least 8 characters");

  if (password.length >= 12) score++;

  // Character type checks
  if (/[a-z]/.test(password)) score += 0.5;
  else suggestions.push("Add lowercase letters");

  if (/[A-Z]/.test(password)) score += 0.5;
  else suggestions.push("Add uppercase letters");

  if (/[0-9]/.test(password)) score += 0.5;
  else suggestions.push("Add numbers");

  if (/[^a-zA-Z0-9]/.test(password)) score += 0.5;
  else suggestions.push("Add special characters");

  // Normalize score to 0-4
  score = Math.min(4, Math.round(score));

  const labels: PasswordStrength["label"][] = [
    "Very Weak",
    "Weak",
    "Fair",
    "Strong",
    "Very Strong",
  ];

  const colors = [
    "bg-red-500",
    "bg-orange-500",
    "bg-yellow-500",
    "bg-lime-500",
    "bg-green-500",
  ];

  return {
    score,
    label: labels[score],
    suggestions: score < 3 ? suggestions : [],
    color: colors[score],
  };
}
