importScripts("./spark-md5.min.js")

onmessage = (e) => {
    let {file, chunkSize} = e.data;
    let hashList = [];

    const chunkHandler = async filePart => new Promise(res => {
        let reader = new FileReader();
        let spark = new SparkMD5.ArrayBuffer();
        reader.readAsArrayBuffer(filePart);
        reader.onload = (r) => {
            let chunk = r.target.result;
            spark.append(chunk);
            res({
                chunk: new Blob([chunk]),
                hash: spark.end()
            });
        }
    });

    let total = Math.ceil(file.size / chunkSize);
    let index = 0;
    const mainLoop = async () => {
        while(index < total){
            const start = index * chunkSize;
            const end = Math.min(file.size, start + chunkSize);
            const fileSlice = file.slice(start, end);
            let res = await chunkHandler(fileSlice);
            index++;
            if(index > total){
                postMessage(hashList);
                break;
            }
            hashList.push(res);
        }
    }
    mainLoop().then();
}