# Railway Deployment Guide for SkillStudio

## ✅ Files Created for Deployment

1. **Procfile** - Tells Railway how to start your app
2. **runtime.txt** - Specifies Python version
3. **railway.json** - Railway configuration
4. **requirements.txt** - Updated with production dependencies

## 🚀 Step-by-Step Deployment

### Step 1: Create Railway Account
1. Go to [Railway.app](https://railway.app/)
2. Click "Login with GitHub"
3. Authorize Railway to access your repositories

### Step 2: Push Your Code to GitHub
```bash
# Initialize git if not already done
git init

# Add all files
git add .

# Commit
git commit -m "Prepare for Railway deployment"

# Create a new repository on GitHub, then:
git remote add origin https://github.com/YOUR_USERNAME/skillstudio.git
git branch -M main
git push -u origin main
```

### Step 3: Create New Project on Railway
1. Click "New Project"
2. Select "Deploy from GitHub repo"
3. Choose your `skillstudio` repository
4. Railway will automatically detect it's a Django app

### Step 4: Add PostgreSQL Database
1. In your Railway project dashboard
2. Click "New" → "Database" → "Add PostgreSQL"
3. Railway automatically creates `DATABASE_URL` environment variable

### Step 5: Add Environment Variables
Click on your Django service → "Variables" tab → Add these:

```
DJANGO_SECRET_KEY=your-super-secret-key-here-change-this
DEBUG=False
DATABASE_URL=(auto-created by Railway PostgreSQL)
RAILWAY_PUBLIC_DOMAIN=(auto-filled by Railway)
```

**Generate a SECRET_KEY:**
```python
# Run this in Python terminal
from django.core.management.utils import get_random_secret_key
print(get_random_secret_key())
```

### Step 6: Optional - Add Redis (for Channels/Live Sessions)
1. Click "New" → "Database" → "Add Redis"
2. Add environment variable:
```
REDIS_URL=(auto-created by Railway Redis)
```

### Step 7: Deploy
1. Railway automatically deploys on push
2. Wait for build to complete (2-5 minutes)
3. Click "Generate Domain" to get your public URL

### Step 8: Run Migrations
1. In Railway dashboard, go to your service
2. Click "Settings" → "Deploy Triggers"
3. Or use Railway CLI:

```bash
# Install Railway CLI
npm i -g @railway/cli

# Login
railway login

# Link to your project
railway link

# Run migrations
railway run python manage.py migrate

# Create superuser
railway run python manage.py createsuperuser
```

## 🎉 Your App is Live!

Access your app at: `https://your-app-name.up.railway.app`

### Admin Panel
`https://your-app-name.up.railway.app/admin/`

### API
`https://your-app-name.up.railway.app/api/`

## 🔧 Useful Railway Commands

```bash
# View logs
railway logs

# Open app in browser
railway open

# Run Django commands
railway run python manage.py <command>

# Connect to PostgreSQL
railway run python manage.py dbshell
```

## 📝 Next Steps After Deployment

1. **Create superuser**: `railway run python manage.py createsuperuser`
2. **Collect static files**: Auto-done during deployment
3. **Test your endpoints**
4. **Set up custom domain** (Optional - in Railway settings)

## 🐛 Troubleshooting

### Build Failed?
- Check Railway logs for errors
- Verify all dependencies in requirements.txt
- Ensure Python version matches runtime.txt

### Database Connection Error?
- Verify DATABASE_URL is set
- Check PostgreSQL service is running
- Run migrations: `railway run python manage.py migrate`

### Static Files Not Loading?
- Verify WhiteNoise is in MIDDLEWARE
- Check STATIC_ROOT and STATIC_URL settings
- Run: `railway run python manage.py collectstatic --noinput`

### 500 Internal Server Error?
- Set DEBUG=True temporarily to see errors
- Check Railway logs: `railway logs`
- Verify all environment variables are set

## 💰 Pricing

- **Hobby Plan**: $5/month
- Includes 500 hours of usage
- PostgreSQL and Redis included
- Custom domains available

## 🔒 Security Checklist

✅ DEBUG=False in production  
✅ Unique SECRET_KEY set  
✅ ALLOWED_HOSTS configured  
✅ Database credentials secured (via Railway env vars)  
✅ CORS settings properly configured  

## 📚 Additional Resources

- [Railway Docs](https://docs.railway.app/)
- [Django Deployment Checklist](https://docs.djangoproject.com/en/stable/howto/deployment/checklist/)
- [Railway Discord](https://discord.gg/railway) - For support

---

**Need help?** Check Railway logs first: `railway logs --follow`
