import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Loader2, Eye, EyeOff } from 'lucide-react';
import { loginApi } from '../api/auth';
import { useAuthStore } from '../store/authStore';

export default function LoginPage() {
  const navigate = useNavigate();
  const { setAuth } = useAuthStore();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email.trim() || !password) return;

    setLoading(true);
    setError(null);

    try {
      const data = await loginApi(email.trim(), password);
      setAuth(data.user, data.access_token);
      navigate('/', { replace: true });
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#0e0e13] flex items-center justify-center px-4">
      <div className="w-full max-w-sm">
        {/* Logo */}
        <div className="flex flex-col items-center mb-8">
          <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-[#00a8e8] to-[#0077b8] flex items-center justify-center text-white text-2xl font-bold shadow-lg shadow-[#00a8e8]/25 mb-4">
            D
          </div>
          <h1 className="text-xl font-semibold text-[#eeeef8]">Doc Agent</h1>
          <p className="text-sm text-[#4a4a5a] mt-1">by TechChefz</p>
        </div>

        {/* Card */}
        <div className="bg-[#18181f] border border-[#252530] rounded-2xl p-6 shadow-2xl shadow-black/40">
          <h2 className="text-base font-semibold text-[#eeeef8] mb-5">Sign in to your account</h2>

          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Email */}
            <div>
              <label className="block text-xs font-medium text-[#6a6a80] mb-1.5">
                Email address
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                required
                autoFocus
                className="w-full bg-[#111118] border border-[#252530] rounded-xl px-3.5 py-2.5 text-sm text-[#eeeef8] placeholder-[#3a3a4a] outline-none focus:border-[#00a8e8]/50 focus:shadow-sm focus:shadow-[#00a8e8]/10 transition-all"
              />
            </div>

            {/* Password */}
            <div>
              <label className="block text-xs font-medium text-[#6a6a80] mb-1.5">
                Password
              </label>
              <div className="relative">
                <input
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  required
                  className="w-full bg-[#111118] border border-[#252530] rounded-xl px-3.5 py-2.5 pr-10 text-sm text-[#eeeef8] placeholder-[#3a3a4a] outline-none focus:border-[#00a8e8]/50 focus:shadow-sm focus:shadow-[#00a8e8]/10 transition-all"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-[#4a4a5a] hover:text-[#8a8aaa] transition-colors"
                >
                  {showPassword ? <EyeOff size={15} /> : <Eye size={15} />}
                </button>
              </div>
            </div>

            {/* Error */}
            {error && (
              <div className="px-3.5 py-2.5 bg-red-950/40 border border-red-900/50 rounded-xl">
                <p className="text-xs text-red-400">{error}</p>
              </div>
            )}

            {/* Submit */}
            <button
              type="submit"
              disabled={loading || !email.trim() || !password}
              className="w-full flex items-center justify-center gap-2 py-2.5 rounded-xl text-sm font-semibold bg-[#00a8e8] text-white hover:bg-[#0090cc] disabled:opacity-50 disabled:cursor-not-allowed transition-colors shadow-sm shadow-[#00a8e8]/30 mt-1"
            >
              {loading ? (
                <>
                  <Loader2 size={15} className="spinner" />
                  Signing in…
                </>
              ) : (
                'Sign in'
              )}
            </button>
          </form>
        </div>

        <p className="text-center text-xs text-[#2e2e3e] mt-5">
          Don't have an account? Contact your administrator.
        </p>
      </div>
    </div>
  );
}
