
### Hello 👋

I'm studying for a master's degree and looking for PhD opportunity. I'm interested in algorithms, parallel computing, graph computing, HPC,  and databases. I've won a silver medal in ICPC and a bronze medal in the ICPC East Continental Final. For more details, you are welcome to have a view of my [CV here](https://concyclics.github.io/resume/latex/resume.pdf).

You can find me by

- [Github](https://github.com/Concyclics)
- [Linkedin](https://www.linkedin.com/in/han-chen-74784a233/)
- [Gitee](https://gitee.com/concyclics)
- [Kaggle](https://www.kaggle.com/concyclics)
- mail: [concyclics@qq.com](mailto:concyclics@qq.com)
- mail: [chenhan@u.nus.edu](mailto:chenhan@u.nus.edu)
- mail: [chenhan@comp.nus.edu.sg](mailto:chenhan@comp.nus.edu.sg)
- mail: [concyclics@gmail.com](mailto:concyclics@gmail.com)
- wechat: concyclics

<!--[![Rock's Top Langs](https://github-readme-stats.vercel.app/api/top-langs/?username=Concyclics&theme=onedark)](https://github.com/anuraghazra/github-readme-stats)  -->
[![Rock's github stats](https://github-readme-stats.vercel.app/api?username=Concyclics&theme=onedark)](https://github.com/anuraghazra/github-readme-stats)  

<!--[![Anurag's github stats](https://github-readme-stats.vercel.app/api?username=Concyclics&show_icons=true&theme=tokyonight)](https://github.com/Concyclics/github-readme-stats)-->

<!--<img align="right" src="https://github-readme-stats.vercel.app/api/top-langs/?username=Concyclics&layout=compact&theme=tokyonight" />-->

<!--[![Top Langs](https://github-readme-stats.vercel.app/api/top-langs/?username=Concyclics&layout=compact&theme=tokyonight)](https://github.com/Concyclics/github-readme-stats)-->

<!--
**Concyclics/Concyclics** is a ✨ _special_ ✨ repository because its `README.md` (this file) appears on your GitHub profile.

Here are some ideas to get you started:

- 🔭 I’m currently working on ...
- 🌱 I’m currently learning ...
- 👯 I’m looking to collaborate on ...
- 🤔 I’m looking for help with ...
- 💬 Ask me about ...
- 📫 How to reach me: ...
- 😄 Pronouns: ...
- ⚡ Fun fact: ...

急事请呼：18148778939//蓝色闪电号呼叫基地，蓝色闪电号呼叫基地。这里是华为溪村基地，请讲。我蓝色闪电号舰长亚蒙，请求追击离职人员。接过来，这里是部长，你舰是否全员就位，进入待发状态。蓝色闪电已经进入待发状态。批准请求，准备出击。这里是溪村E区，蓝色闪电请按照流程进行准备动作，前方净空，等等，你在干什么。『蓝色闪电』，前进四。

-->
<!--- 🌱 I’m currently learning on South China University of Technology and I graduated from Fuzhou NO.3 Middle School.-->

# %%
Z = [1.0, 2.0]


# %%
def loss(X, Y):
    return (X[0]**2 -X[1]**2 - Y[0])**2 + (2*X[0]*X[1] -Y[1])**2


# %%
def grad(X, Y, lr=0.1):
    new_X = X.copy()
    new_X[0] -= lr * 4 * ((X[0]**2 -X[1]**2 - Y[0]) * X[0] + (2*X[0]*X[1] -Y[1]))
    new_X[1] -= lr * 4 * ((X[0]**2 -X[1]**2 - Y[0]) * (-X[1]) + (2*X[0]*X[1] -Y[1]))
    return new_X


# %%
X = [0.5, 0.5]
print("loss beofre: ", loss(X, Z))
for _ in range(10):
    X = grad(X, Z)
    print(f"iter {_} loss: ", loss(X, Z))
