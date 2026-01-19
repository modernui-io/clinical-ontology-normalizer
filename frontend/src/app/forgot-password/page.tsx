"use client";

import { useState } from "react";
import Link from "next/link";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Loader2, Mail, ArrowLeft, CheckCircle2 } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { useAuth } from "@/hooks/use-auth";

// ============================================================================
// Form Schema
// ============================================================================

const forgotPasswordSchema = z.object({
  email: z.string().email("Please enter a valid email address"),
});

type ForgotPasswordFormData = z.infer<typeof forgotPasswordSchema>;

// ============================================================================
// Success State Component
// ============================================================================

function SuccessState({ email }: { email: string }) {
  return (
    <div className="flex min-h-screen items-center justify-center p-4 bg-gradient-to-br from-muted/30 via-background to-muted/50">
      <div className="w-full max-w-md">
        <Card className="border-0 shadow-lg">
          <CardHeader className="text-center pb-2">
            <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-green-100 dark:bg-green-900/30">
              <CheckCircle2 className="h-8 w-8 text-green-600 dark:text-green-500" />
            </div>
            <CardTitle className="text-xl">Check your email</CardTitle>
            <CardDescription className="mt-2">
              We&apos;ve sent a password reset link to
            </CardDescription>
          </CardHeader>

          <CardContent className="text-center space-y-4">
            <p className="font-medium text-foreground">{email}</p>

            <div className="rounded-lg bg-muted/50 p-4 text-sm text-muted-foreground">
              <p>
                Click the link in the email to reset your password. If you
                don&apos;t see the email, check your spam folder.
              </p>
            </div>

            <p className="text-xs text-muted-foreground">
              The link will expire in 1 hour.
            </p>
          </CardContent>

          <CardFooter className="flex flex-col space-y-4">
            <Button asChild variant="outline" className="w-full">
              <Link href="/login">
                <ArrowLeft className="mr-2 h-4 w-4" />
                Back to login
              </Link>
            </Button>

            <p className="text-center text-xs text-muted-foreground">
              Didn&apos;t receive the email?{" "}
              <button
                onClick={() => window.location.reload()}
                className="font-medium text-primary hover:underline"
              >
                Try again
              </button>
            </p>
          </CardFooter>
        </Card>
      </div>
    </div>
  );
}

// ============================================================================
// Forgot Password Page Component
// ============================================================================

export default function ForgotPasswordPage() {
  const { forgotPassword, isLoading, error, clearError } = useAuth();
  const [submitted, setSubmitted] = useState(false);
  const [submittedEmail, setSubmittedEmail] = useState("");

  const form = useForm<ForgotPasswordFormData>({
    resolver: zodResolver(forgotPasswordSchema),
    defaultValues: {
      email: "",
    },
  });

  const onSubmit = async (data: ForgotPasswordFormData) => {
    clearError();

    const success = await forgotPassword(data.email);

    if (success) {
      setSubmittedEmail(data.email);
      setSubmitted(true);
      toast.success("Email sent", {
        description: "Check your inbox for the password reset link.",
      });
    } else {
      toast.error("Request failed", {
        description: error || "Please try again.",
      });
    }
  };

  if (submitted) {
    return <SuccessState email={submittedEmail} />;
  }

  return (
    <div className="flex min-h-screen items-center justify-center p-4 bg-gradient-to-br from-muted/30 via-background to-muted/50">
      <div className="w-full max-w-md">
        {/* Logo / Branding */}
        <div className="mb-8 text-center">
          <h1 className="text-2xl font-bold tracking-tight">
            Clinical Ontology Normalizer
          </h1>
          <p className="text-muted-foreground mt-2">Reset your password</p>
        </div>

        <Card className="border-0 shadow-lg">
          <CardHeader className="space-y-1 pb-4">
            <CardTitle className="text-xl">Forgot your password?</CardTitle>
            <CardDescription>
              Enter your email address and we&apos;ll send you a link to reset
              your password.
            </CardDescription>
          </CardHeader>

          <CardContent>
            <Form {...form}>
              <form
                onSubmit={form.handleSubmit(onSubmit)}
                className="space-y-4"
              >
                <FormField
                  control={form.control}
                  name="email"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Email address</FormLabel>
                      <FormControl>
                        <div className="relative">
                          <Mail className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                          <Input
                            placeholder="name@example.com"
                            type="email"
                            autoComplete="email"
                            className="pl-10"
                            {...field}
                          />
                        </div>
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                {error && (
                  <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
                    {error}
                  </div>
                )}

                <Button type="submit" className="w-full" disabled={isLoading}>
                  {isLoading ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Sending email...
                    </>
                  ) : (
                    "Send reset link"
                  )}
                </Button>
              </form>
            </Form>
          </CardContent>

          <CardFooter className="flex justify-center pt-0">
            <Link
              href="/login"
              className="flex items-center text-sm text-muted-foreground hover:text-foreground"
            >
              <ArrowLeft className="mr-2 h-4 w-4" />
              Back to login
            </Link>
          </CardFooter>
        </Card>

        {/* Help text */}
        <p className="mt-6 text-center text-xs text-muted-foreground">
          Remember your password?{" "}
          <Link href="/login" className="text-primary hover:underline">
            Sign in instead
          </Link>
        </p>
      </div>
    </div>
  );
}
